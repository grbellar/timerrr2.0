import os
import stripe
from flask import Blueprint, request, jsonify, redirect, url_for, flash
from flask_login import current_user, login_required
from app.models import db, User, TierEnum
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

stripe_bp = Blueprint('stripe_bp', __name__)

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
STRIPE_PRO_PRICE_ID = os.environ.get('STRIPE_PRO_PRICE_ID', '')
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5001')

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
            success_url=BASE_URL + '/stripe/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=BASE_URL + '/settings',
            customer_email=current_user.email,
            client_reference_id=str(current_user.id),
            # Enable promotion codes for marketing campaigns
            allow_promotion_codes=True,
            # Collect billing address for tax compliance
            billing_address_collection='auto',
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

    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    if not sig_header:
        logger.error("Missing Stripe-Signature header")
        return jsonify({'error': 'Missing signature'}), 400

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {e}")
        return jsonify({'error': 'Invalid signature'}), 400

    # Log all webhook events for debugging
    logger.info(f"Received Stripe webhook: {event['type']}")

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        logger.info(f"Processing checkout.session.completed for session {session.get('id')}")

        # Verify this is a subscription session
        if session.get('mode') != 'subscription':
            logger.info(f"Skipping non-subscription checkout session {session.get('id')}")
            return jsonify({'received': True}), 200

        user_id = session.get('client_reference_id')
        if not user_id:
            logger.error("No client_reference_id in checkout session")
            return jsonify({'error': 'Missing user reference'}), 400

        subscription_id = session.get('subscription')
        customer_id = session.get('customer')

        if not subscription_id:
            logger.error(f"No subscription ID in checkout session {session.get('id')}")
            return jsonify({'error': 'Missing subscription ID'}), 400

        try:
            user = User.query.get(int(user_id))
            if user:
                logger.info(f"Found user {user_id}, current tier: {user.tier}")

                # Update user to Pro tier
                user.tier = TierEnum.PRO
                user.stripe_customer_id = customer_id
                user.stripe_subscription_id = subscription_id

                # Only set upgraded_at if this is their first upgrade
                if not user.upgraded_at:
                    user.upgraded_at = datetime.now(timezone.utc)

                db.session.commit()
                logger.info(f"User {user_id} upgraded to Pro tier successfully (subscription: {subscription_id})")

                # Verify the update
                updated_user = User.query.get(int(user_id))
                logger.info(f"User {user_id} tier after update: {updated_user.tier}")
            else:
                logger.error(f"User {user_id} not found")
                return jsonify({'error': 'User not found'}), 404

        except Exception as e:
            logger.error(f"Error updating user tier: {e}")
            db.session.rollback()
            return jsonify({'error': 'Failed to update user'}), 500

    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        logger.info(f"Processing customer.subscription.deleted for subscription {subscription['id']}")

        try:
            user = User.query.filter_by(stripe_subscription_id=subscription['id']).first()
            if user:
                user.tier = TierEnum.FREE
                user.stripe_subscription_id = None
                db.session.commit()
                logger.info(f"User {user.id} downgraded to Free tier (subscription deleted)")
            else:
                logger.warning(f"No user found for subscription {subscription['id']}")

        except Exception as e:
            logger.error(f"Error downgrading user: {e}")
            db.session.rollback()

    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        logger.info(f"Processing customer.subscription.updated for subscription {subscription['id']} with status {subscription['status']}")

        try:
            user = User.query.filter_by(stripe_subscription_id=subscription['id']).first()
            if user:
                subscription_status = subscription['status']
                cancel_at_period_end = subscription.get('cancel_at_period_end', False)

                # Check if subscription is canceled but still active (cancel_at_period_end=True)
                if cancel_at_period_end:
                    # Subscription is canceled but still active until period end
                    # User keeps Pro access until the period ends, then customer.subscription.deleted fires
                    logger.info(f"Subscription {subscription['id']} is set to cancel at period end. User {user.id} keeps Pro access until then.")
                    # Don't downgrade yet - wait for customer.subscription.deleted event

                # Statuses that grant Pro access: active, trialing
                # Stripe subscription statuses: incomplete, incomplete_expired, trialing, active, past_due, canceled, unpaid
                elif subscription_status in ['active', 'trialing']:
                    # Grant Pro access
                    if user.tier != TierEnum.PRO:
                        user.tier = TierEnum.PRO
                        if not user.upgraded_at:
                            user.upgraded_at = datetime.now(timezone.utc)
                        db.session.commit()
                        logger.info(f"User {user.id} upgraded to Pro tier (subscription {subscription_status})")

                # Statuses that should downgrade to Free: canceled, unpaid, past_due, incomplete_expired
                elif subscription_status in ['canceled', 'unpaid', 'incomplete_expired']:
                    # Remove Pro access - these are terminal/failed states
                    if user.tier != TierEnum.FREE:
                        user.tier = TierEnum.FREE
                        db.session.commit()
                        logger.info(f"User {user.id} downgraded to Free tier (subscription {subscription_status})")

                    # Clear subscription ID for terminal states
                    if subscription_status in ['canceled', 'incomplete_expired']:
                        user.stripe_subscription_id = None
                        db.session.commit()
                        logger.info(f"Cleared subscription ID for user {user.id}")

                # past_due: Keep subscription ID but downgrade access while payment is being retried
                elif subscription_status == 'past_due':
                    if user.tier != TierEnum.FREE:
                        user.tier = TierEnum.FREE
                        db.session.commit()
                        logger.info(f"User {user.id} downgraded to Free tier (payment past due)")

                # incomplete: Initial state, don't grant access yet but don't downgrade existing
                elif subscription_status == 'incomplete':
                    logger.info(f"Subscription {subscription['id']} is incomplete, no action taken")

            else:
                logger.warning(f"No user found for subscription {subscription['id']}")

        except Exception as e:
            logger.error(f"Error updating user subscription: {e}")
            db.session.rollback()

    elif event['type'] == 'invoice.payment_failed':
        # Handle failed recurring payments
        invoice = event['data']['object']
        subscription_id = invoice.get('subscription')

        if subscription_id:
            logger.info(f"Processing invoice.payment_failed for subscription {subscription_id}")

            try:
                user = User.query.filter_by(stripe_subscription_id=subscription_id).first()
                if user:
                    # Don't immediately downgrade - Stripe will retry based on your settings
                    # The subscription.updated event will handle the actual downgrade if retries fail
                    logger.warning(f"Payment failed for user {user.id}, subscription {subscription_id}. Stripe will retry.")
                else:
                    logger.warning(f"No user found for subscription {subscription_id} with failed payment")

            except Exception as e:
                logger.error(f"Error handling failed payment: {e}")

    return jsonify({'received': True}), 200

@stripe_bp.route('/api/stripe/debug/user', methods=['GET'])
@login_required
def debug_user():
    """Debug endpoint to check user tier and Stripe data"""
    return jsonify({
        'user_id': current_user.id,
        'email': current_user.email,
        'tier': current_user.tier.value,
        'stripe_customer_id': current_user.stripe_customer_id,
        'stripe_subscription_id': current_user.stripe_subscription_id,
        'upgraded_at': current_user.upgraded_at.isoformat() if current_user.upgraded_at else None
    })

@stripe_bp.route('/stripe/success')
@login_required
def payment_success():
    """Handle successful payment redirect"""

    session_id = request.args.get('session_id')

    if session_id and stripe.api_key:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            logger.info(f"Payment success for session {session_id}, status: {session.payment_status}")

            if session.payment_status == 'paid':
                # Check if user is already PRO (webhook might have already processed)
                if current_user.tier == TierEnum.PRO:
                    flash('Successfully upgraded to Pro! Your account has been updated.', 'success')
                else:
                    # Fallback: manually update user if webhook hasn't processed yet
                    try:
                        current_user.tier = TierEnum.PRO
                        current_user.stripe_customer_id = session.get('customer')
                        current_user.stripe_subscription_id = session.get('subscription')
                        current_user.upgraded_at = datetime.now(timezone.utc)
                        db.session.commit()
                        logger.info(f"Fallback: Manually upgraded user {current_user.id} to Pro tier")
                        flash('Successfully upgraded to Pro! Your account has been updated.', 'success')
                    except Exception as e:
                        logger.error(f"Fallback upgrade failed: {e}")
                        flash('Payment successful! Your account will be updated shortly.', 'info')
            else:
                flash('Payment is being processed. Your account will be updated shortly.', 'info')

        except Exception as e:
            logger.error(f"Error retrieving checkout session: {e}")
            flash('Payment received! Your account will be updated shortly.', 'info')
    else:
        flash('Payment successful! Your account will be updated shortly.', 'info')

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
            return_url=BASE_URL + '/settings',
        )

        return jsonify({'portal_url': portal_session.url}), 200

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        return jsonify({'error': 'Failed to create portal session'}), 500
    except Exception as e:
        logger.error(f"Error creating portal session: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500