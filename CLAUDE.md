# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flask-based time tracking application called "timerrr" with a clean, minimal interface built using Tailwind CSS via CDN.

## Development Commands

### Setup and Run
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application with gevent (production-like)
./start.sh
# Or directly:
gunicorn --worker-class gevent --workers 1 --bind 0.0.0.0:5001 wsgi:application --reload
```

The application runs on http://localhost:5001
    
### Virtual Environment
Always ensure the virtual environment is activated before running commands or installing packages.

## Architecture

### Application Structure
- **Flask factory pattern** - App is created via `create_app()` in `app/__init__.py`
- **Blueprint-based routing** - Routes are organized in `app/routes.py` using Flask blueprints
- **Template inheritance** - All HTML templates extend `base.html` for consistent layout
- **Tailwind CSS via CDN** - No build step required for styling
- **Real-time updates** - Socket.IO for WebSocket communication between client and server

### Key Routes
- `/` - Landing page
- `/timer` - Active timer interface with real-time updates
- `/entries` - Time entries list
- `/timesheets` - Timesheet view
- `/settings` - Settings page with Stripe subscription management
- `/api/hello` - Example API endpoint

### Stripe Integration
The application includes Stripe payment processing for Pro tier subscriptions:

#### Configuration
Set the following environment variables in `.env`:
```bash
STRIPE_SECRET_KEY=sk_test_...       # Your Stripe secret key
STRIPE_WEBHOOK_SECRET=whsec_...     # Webhook endpoint signing secret
STRIPE_PRO_PRICE_ID=price_...       # Price ID for Pro subscription
BASE_URL=https://timerrr.app/       # Base URL for redirect URLs (production only)
```

#### Endpoints
- `POST /api/stripe/create-checkout-session` - Creates Stripe checkout session for Pro upgrade
- `POST /api/stripe/webhook` - Handles Stripe webhook events
- `GET /stripe/success` - Success redirect after payment
- `GET /stripe/cancel` - Cancel redirect from checkout
- `POST /api/stripe/customer-portal` - Opens Stripe customer portal for Pro users

#### Webhook Events Handled
- `checkout.session.completed` - Upgrades user to Pro tier after successful payment (subscription mode only)
- `customer.subscription.deleted` - Downgrades user to Free tier when subscription is deleted
- `customer.subscription.updated` - Handles all subscription status changes:
  - `active`, `trialing` → Grant Pro access
  - `canceled`, `unpaid`, `incomplete_expired` → Downgrade to Free (terminal states)
  - `past_due` → Downgrade to Free but keep subscription ID (Stripe will retry)
  - `incomplete` → No action (initial state)
- `invoice.payment_failed` - Logs failed recurring payments (Stripe handles retries)

#### Database Fields
User model includes Stripe-specific fields:
- `tier` - Enum field (FREE/PRO) for subscription status
- `stripe_customer_id` - Stripe customer identifier
- `stripe_subscription_id` - Active subscription ID
- `upgraded_at` - Timestamp of Pro tier upgrade

#### Setup Instructions
1. Create products and prices in Stripe Dashboard
2. Configure webhook endpoint: `https://your-domain.com/api/stripe/webhook`
3. Select webhook events: `checkout.session.completed`, `customer.subscription.deleted`, `customer.subscription.updated`, `invoice.payment_failed`
4. Add environment variables to `.env` file
5. Users can upgrade via Settings page "Upgrade to Pro" button
6. Pro users can manage subscription via "Manage Subscription" button

#### Checkout Session Features
- **Promotion codes enabled** - Users can apply discount codes at checkout
- **Billing address collection** - Automatically collects addresses for tax compliance
- **Subscription validation** - Verifies session mode and subscription ID before processing

### Real-time Features with Socket.IO
The application uses Flask-SocketIO with gevent for real-time timer updates across all user devices:

#### Architecture
- **Gevent async mode** - Uses gevent for efficient async I/O and WebSocket connections
- **Monkey-patching** - `wsgi.py` applies gevent patches before imports (critical for Stripe/HTTP compatibility)
- **Server-side broadcasting** - Events are emitted from API endpoints in `app/timer.py` after database changes
- **User-specific rooms** - Each user joins a room `user_{id}` for isolated broadcasts
- **No page refresh needed** - All timer state changes sync instantly across devices

#### Implementation Details
- **Entry point** - `wsgi.py` performs gevent monkey-patching before importing the app
- **WebSocket events** handled in `app/socketio_events.py`
- **Broadcasting from API** - Timer API endpoints emit Socket.IO events after DB updates
- **Room-based isolation** - Events broadcast to `user_{current_user.id}` room only
- **Event flow**:
  1. User clicks "Clock in" → API call to `/api/clients/{id}/timer/start`
  2. Server creates timer in DB, then broadcasts `timer_started` to user's room
  3. All user's connected devices receive event and update UI instantly

#### Event Types
- `timer_started` - Broadcast when a timer starts (includes timer_id, client_id, start_time)
- `timer_stopped` - Broadcast when a timer stops (includes timer_id, client_id, end_time)
- `notes_updated` - Broadcast when timer notes are updated (includes timer_id, notes)

#### Frontend Integration
- **Client-side Socket.IO** loaded via CDN in timer.html
- **JavaScript timer display** - Updates every second using setInterval
- **UTC timezone handling** - All timestamps use UTC with 'Z' suffix for proper JavaScript parsing
- **Auto-save notes** - Timer notes saved automatically with 500ms debouncing
- **No redundant emissions** - Client only makes API calls, server handles all Socket.IO broadcasts

### Frontend Design System
Templates follow a consistent design pattern documented in `app/templates/CLAUDE.md`:
- Mobile-first responsive design using Tailwind CSS
- Inter font family from Google Fonts
- White cards on gray-50 background
- Consistent spacing and typography scale
- No JavaScript frameworks - vanilla JS with Socket.IO for real-time features
- Modal dialogs with semi-transparent overlay and centered white cards
- Standardized component patterns for empty states, loading states, and data tables

#### Key UI Components
- **Modal dialogs** - Centered white cards with dark overlay, closable via X button, Cancel, Escape key, or clicking outside
- **Form inputs** - Consistent styling with focus rings and proper spacing
- **Buttons** - Primary (dark bg), secondary (text only), danger (red text)
- **Status indicators** - Green dots for running timers
- **Responsive tables** - Stack on mobile, horizontal on desktop