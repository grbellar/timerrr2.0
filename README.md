# Timerrr

A modern, real-time time tracking application built with Flask, featuring live timer synchronization across devices, Stripe payment integration, and automated timesheet generation.

## Features

### Core Functionality
- **Real-time Timer Tracking** - Track time for multiple clients with live updates across all your devices
- **Time Entries Management** - View, edit, and delete time entries with filtering by date and client
- **Client Management** - Add, edit, and manage clients with customizable hourly rates
- **Automated Timesheets** - Generate CSV timesheets for clients with detailed breakdowns

### Premium Features
- **Stripe Integration** - Seamless upgrade to Pro tier with subscription management
- **Customer Portal** - Pro users can manage their subscription through Stripe's customer portal

### Technical Highlights
- **WebSocket Support** - Real-time updates using Flask-SocketIO for instant timer synchronization
- **Responsive Design** - Mobile-first interface built with Tailwind CSS via CDN
- **Secure Authentication** - User accounts with Flask-Login and password hashing
- **SQLite Database** - Lightweight database with SQLAlchemy ORM

## Getting Started

### Prerequisites
- Python 3.11+
- pip
- Virtual environment (recommended)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/timerrr-w-flask.git
cd timerrr-w-flask
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run the application:
```bash
python app.py
# Or use the start script
./start.sh
```

The application runs on http://localhost:5001

## Configuration

### Environment Variables

Create a `.env` file in the project root with:

```bash
# Flask Configuration
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///timerrr.db

# Stripe Configuration (Optional - for Pro features)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRO_PRICE_ID=price_...
```

### Stripe Setup (For Payment Features)

1. Create a Stripe account at [stripe.com](https://stripe.com)
2. Get your API keys from the [Stripe Dashboard](https://dashboard.stripe.com/apikeys)
3. Create a product and recurring price ($7/month) for the Pro plan
4. Set up webhook endpoint:
   - URL: `https://your-domain.com/api/stripe/webhook`
   - Events to listen for:
     - `checkout.session.completed`
     - `customer.subscription.deleted`
     - `customer.subscription.updated`
5. Add all keys to your `.env` file

## Project Structure

```
timerrr-w-flask/
├── app/
│   ├── __init__.py           # App factory and configuration
│   ├── auth.py               # Authentication routes
│   ├── main.py               # Main application routes
│   ├── client.py             # Client management API
│   ├── timer.py              # Timer functionality
│   ├── entries.py            # Time entries management
│   ├── timesheets.py         # Timesheet generation
│   ├── stripe.py             # Stripe payment integration
│   ├── socketio_events.py    # WebSocket event handlers
│   ├── models.py             # Database models
│   ├── templates/            # HTML templates
│   │   ├── base.html         # Base template
│   │   ├── index.html        # Landing page
│   │   ├── timer.html        # Timer interface
│   │   ├── entries.html      # Time entries view
│   │   ├── timesheets.html   # Timesheet management
│   │   ├── settings.html     # User settings
│   │   └── CLAUDE.md         # Template design documentation
│   └── static/               # Static assets
├── .venv/                    # Virtual environment (not in git)
├── .env                      # Environment variables (not in git)
├── .env.example              # Example environment configuration
├── .gitignore
├── requirements.txt          # Python dependencies
├── app.py                    # Application entry point
├── start.sh                  # Startup script
├── CLAUDE.md                 # Development documentation
└── README.md                 # This file
```

## API Endpoints

### Authentication
- `POST /login` - User login
- `GET /logout` - User logout
- `POST /register` - Create new account

### Timer Management
- `POST /api/clients/{id}/timer/start` - Start timer for client
- `POST /api/timers/{id}/stop` - Stop running timer
- `PUT /api/timers/{id}/notes` - Update timer notes

### Client Management
- `GET /api/clients` - List all clients
- `POST /api/clients` - Create new client
- `PUT /api/clients/{id}` - Update client
- `DELETE /api/clients/{id}` - Delete client

### Time Entries
- `GET /api/entries` - Get filtered time entries
- `PUT /api/entries/{id}` - Update entry
- `DELETE /api/entries/{id}` - Delete entry

### Timesheets
- `GET /api/timesheets` - List all timesheets
- `POST /api/timesheets/generate` - Generate new timesheet
- `GET /api/timesheets/{id}/download` - Download timesheet CSV
- `DELETE /api/timesheets/{id}` - Delete timesheet

### Stripe Integration
- `POST /api/stripe/create-checkout-session` - Start Pro upgrade
- `POST /api/stripe/webhook` - Handle Stripe webhooks
- `POST /api/stripe/customer-portal` - Access subscription management

## WebSocket Events

The application uses Socket.IO for real-time updates:

### Events Emitted by Server
- `timer_started` - When a timer starts (includes timer_id, client_id, start_time)
- `timer_stopped` - When a timer stops (includes timer_id, client_id, end_time)
- `notes_updated` - When timer notes are updated (includes timer_id, notes)

### Room-based Broadcasting
- Each user joins a room `user_{id}` for isolated real-time updates
- All timer events are broadcast only to the user's connected devices

## Database Schema

### Users
- `id` - Primary key
- `email` - Unique email address
- `password_hash` - Encrypted password
- `tier` - Subscription tier (FREE/PRO)
- `stripe_customer_id` - Stripe customer identifier
- `stripe_subscription_id` - Active subscription ID
- `upgraded_at` - Pro tier upgrade timestamp
- `created_at` - Account creation timestamp

### Clients
- `id` - Primary key
- `name` - Client name
- `user_id` - Associated user
- `hourly_rate` - Billing rate
- `created_at` - Creation timestamp

### TimeEntries
- `id` - Primary key
- `user_id` - Associated user
- `client_id` - Associated client
- `start_time` - Timer start
- `end_time` - Timer end (null if running)
- `notes` - Task description
- `created_at` - Entry creation timestamp

### Timesheets
- `id` - Primary key
- `user_id` - Associated user
- `client_id` - Associated client
- `month` - Timesheet month (1-12)
- `year` - Timesheet year
- `total_hours` - Total hours worked
- `total_amount` - Total billing amount
- `csv_data` - Generated CSV content
- `created_at` - Generation timestamp

## Development

### Running in Development Mode

```bash
# With debug mode enabled
python app.py

# The app will auto-reload on code changes
```

### Testing

```bash
# Run with test Stripe keys
export STRIPE_SECRET_KEY=sk_test_...
python app.py
```

### Database Migrations

The database schema is automatically created on first run. To reset:

```bash
# Delete the database file
rm timerrr.db

# Restart the app to recreate tables
python app.py
```

## Deployment

### Production Considerations

1. **Environment Variables**: Use strong, unique SECRET_KEY
2. **Database**: Consider PostgreSQL for production
3. **HTTPS**: Required for Stripe webhooks
4. **WSGI Server**: Use Gunicorn or similar (included in requirements.txt)
5. **Static Files**: Consider CDN for production
6. **Monitoring**: Set up logging and error tracking

### Example Gunicorn Command

```bash
gunicorn -w 4 -b 0.0.0.0:5001 --worker-class eventlet app:app
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is proprietary software. All rights reserved.

## Support

For issues, questions, or feedback, please open an issue on GitHub or contact the development team.

## Acknowledgments

- Built with [Flask](https://flask.palletsprojects.com/)
- Styled with [Tailwind CSS](https://tailwindcss.com/)
- Payments powered by [Stripe](https://stripe.com/)
- Real-time features via [Socket.IO](https://socket.io/)