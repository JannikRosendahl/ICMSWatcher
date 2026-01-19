# ICMS Watcher

Automates the process of logging into the hsh-campusmanagement (switching role to student), scraping grades, and sending alerts via Telegram. It utilizes Selenium for web automation and requires specific environment variables for configuration.

## Configuration

Create a `.env` file in the project root with the required environment variables:

```bash
ICMS_TG_API_TOKEN=<your-telegram-bot-token>
ICMS_USERNAME=<your-icms-username>
ICMS_PASSWORD=<your-icms-password>
ICMS_TG_ID=<your-telegram-chat-id>
```

## Usage

### Scheduled Mode (Cron)

Runs the application at regular intervals. Configure the schedule in `docker-compose.yml`:

```bash
docker compose up -d
```

Edit `CRON_SCHEDULE` in `docker-compose.yml` to change the interval (default: every 30 minutes):
- `*/30 * * * *` - every 30 minutes
- `0 */2 * * *` - every 2 hours
- `0 8 * * *` - daily at 8 AM

View logs:
```bash
docker compose logs -f icms-watcher
```

### One-Shot Mode

Run the application once and exit:

```bash
docker compose run --build --rm icms-watcher sh -c "RUN_ONCE=true docker-entrypoint.sh"
```