# GitHub Secrets Checklist

Add these under **Repository Settings → Secrets and variables → Actions**.

- [ ] `SMTP_HOST` = `smtp.gmail.com`
- [ ] `SMTP_PORT` = `465`
- [ ] `SMTP_USERNAME` = Gmail sender address
- [ ] `SMTP_PASSWORD` = Gmail 16-character App Password
- [ ] `SMTP_FROM` = same Gmail sender address

Recipient is already set in the workflow:

```text
abhayv7272@gmail.com
```

## Never commit

- Normal Gmail password
- Gmail App Password
- Broker API secret
- Access token
- `.env` file
- Private key

If the App Password is accidentally committed or shown in logs, revoke it immediately in the Google Account and create a new one.

## Optional future broker/vendor secrets

Only add these if a licensed adapter is implemented later:

- `BROKER_API_KEY`
- `BROKER_API_SECRET`
- `BROKER_ACCESS_TOKEN`
- `MARKET_DATA_API_KEY`

The current free-source pipeline does not require these.
