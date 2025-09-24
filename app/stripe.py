import os
import stripe
from flask import Blueprint, request, jsonify, redirect, url_for, flash
from flask_login import current_user, login_required
from app.models import db, User, TierEnum
from datetime import datetime, timezone
import logging
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

stripe_bp = Blueprint('stripe_bp', __name__)

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
STRIPE_PRO_PRICE_ID = os.environ.get('STRIPE_PRO_PRICE_ID', '')

if not stripe.api_key:
    logger.warning("STRIPE_SECRET_KEY not configured. Stripe functionality will not work.")

@stripe_bp.route('/api/stripe/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    """Create a Stripe checkout session for Pro plan upgrade"""

    if not stripe.api_key or not STRIPE_PRO_PRICE_ID:
        return jsonify({'error': 'Stripe is not configured'}), 503

    if current_user.tier == TierEnum.PRO:
        return jsonify({'error': 'User already has Pro tier'}), 400

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{
                'price': STRIPE_PRO_PRICE_ID,
                'quantity': 1,
            }],
            success_url=request.host_url + 'stripe/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.host_url + 'settings',
            customer_email=current_user.email,
            client_reference_id=str(current_user.id),
            metadata={
                'user_id': str(current_user.id),
                'user_email': current_user.email
            }
        )

        return jsonify({'checkout_url': checkout_session.url}), 200

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {e}")
        return jsonify({'error': 'Failed to create checkout session'}), 500
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@stripe_bp.route('/api/stripe/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""

    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not configured")
        return jsonify({'error': 'Webhook secret not configured'}), 503

    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid webhook payload")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        return jsonify({'error': 'Invalid signature'}), 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        user_id = session.get('client_reference_id')
        if not user_id:
            logger.error("No client_reference_id in checkout session")
            return jsonify({'error': 'Missing user reference'}), 400

        try:
            user = User.query.get(int(user_id))
            if user:
                user.tier = TierEnum.PRO
                user.stripe_customer_id = session.get('customer')
                user.stripe_subscription_id = session.get('subscription')
                user.upgraded_at = datetime.now(timezone.utc)
                db.session.commit()
                logger.info(f"User {user_id} upgraded to Pro tier")
            else:
                logger.error(f"User {user_id} not found")
                return jsonify({'error': 'User not found'}), 404

        except Exception as e:
            logger.error(f"Error updating user tier: {e}")
            db.session.rollback()
            return jsonify({'error': 'Failed to update user'}), 500

    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']

        try:
            user = User.query.filter_by(stripe_subscription_id=subscription['id']).first()
            if user:
                user.tier = TierEnum.FREE
                user.stripe_subscription_id = None
                db.session.commit()
                logger.info(f"User {user.id} downgraded to Free tier (subscription deleted)")

        except Exception as e:
            logger.error(f"Error downgrading user: {e}")
            db.session.rollback()

    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']

        try:
            user = User.query.filter_by(stripe_subscription_id=subscription['id']).first()
            if user:
                # Check subscription status
                if subscription['status'] in ['canceled', 'unpaid', 'past_due']:
                    user.tier = TierEnum.FREE
                    if subscription['status'] == 'canceled':
                        user.stripe_subscription_id = None
                    db.session.commit()
                    logger.info(f"User {user.id} downgraded to Free tier (subscription {subscription['status']})")
                elif subscription['status'] == 'active':
                    user.tier = TierEnum.PRO
                    db.session.commit()
                    logger.info(f"User {user.id} subscription reactivated to Pro tier")

        except Exception as e:
            logger.error(f"Error updating user subscription: {e}")
            db.session.rollback()

    return jsonify({'received': True}), 200

@stripe_bp.route('/stripe/success')
@login_required
def payment_success():
    """Handle successful payment redirect"""

    session_id = request.args.get('session_id')

    if session_id and stripe.api_key:
        try:
            session = stripe.checkout.Session.retrieve(session_id)

            if session.payment_status == 'paid':
                flash('Successfully upgraded to Pro! Your account has been updated.', 'success')
            else:
                flash('Payment is being processed. Your account will be updated shortly.', 'info')

        except Exception as e:
            logger.error(f"Error retrieving checkout session: {e}")
            flash('Payment received! Your account will be updated shortly.', 'info')

    return redirect(url_for('main.settings'))

@stripe_bp.route('/stripe/cancel')
@login_required
def payment_cancel():
    """Handle cancelled payment redirect"""
    flash('Upgrade cancelled. You can upgrade anytime from settings.', 'info')
    return redirect(url_for('main.settings'))

@stripe_bp.route('/api/stripe/customer-portal', methods=['POST'])
@login_required
def create_customer_portal_session():
    """Create a Stripe customer portal session for managing subscription"""

    if not stripe.api_key:
        return jsonify({'error': 'Stripe is not configured'}), 503

    if current_user.tier != TierEnum.PRO:
        return jsonify({'error': 'User does not have an active subscription'}), 400

    if not hasattr(current_user, 'stripe_customer_id') or not current_user.stripe_customer_id:
        return jsonify({'error': 'No customer ID found'}), 400

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=request.host_url + 'settings',
        )

        return jsonify({'portal_url': portal_session.url}), 200

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        return jsonify({'error': 'Failed to create portal session'}), 500
    except Exception as e:
        logger.error(f"Error creating portal session: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500