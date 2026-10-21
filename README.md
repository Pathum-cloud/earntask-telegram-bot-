# EarnTask Telegram Bot (Starter Project)

A Python starter project for a Telegram task-and-referral bot using aiogram, FastAPI, and Neon PostgreSQL.

## Important security notice

Never commit `.env`, bot tokens, database URLs, database passwords, private keys, or user secrets to GitHub. If a database password or connection string was shared publicly, rotate it in the Neon dashboard and use the new credential. Configure secrets in your hosting provider's Environment Variables / Secrets settings.

## Features

- English-language Telegram menu and bot messages
- Required-channel membership gate
- Referral tracking and configurable referral reward
- Task submission requests with manual USDT BEP20 payment review
- Admin approval/rejection controls for task requests
- Admin-only command to add free tasks
- Membership verification for supported public Telegram groups/channels
- Withdrawal requests with admin review
- Adsbitvex browser SDK example page
- PostgreSQL storage through Neon

## Environment variables

Copy `.env.example` values into your hosting provider's environment variable settings and replace every placeholder:

- `BOT_TOKEN`: token from Telegram BotFather
- `ADMIN_ID`: your numeric Telegram user ID
- `DATABASE_URL`: Neon PostgreSQL connection string
- `CHANNEL_1`, `CHANNEL_2`: required Telegram channel usernames, such as `@examplechannel`
- `PUBLIC_BASE_URL`: public HTTPS URL of this service
- Optional pricing and reward settings are documented in `.env.example`

Do not upload a real `.env` file to GitHub. The bot should be an administrator in required channels for membership checks to work reliably.

## Run locally

```bash
python -m pip install -r requirements.txt
python main.py
```

The app serves a health endpoint at `/` and an ad page at `/ad?uid=TELEGRAM_USER_ID`.

## Deployment notes

This starter runs Telegram long polling and the FastAPI web server in one Python process. A compatible host must allow the process to remain running. Free web-service plans may sleep or stop background processing, so continuous bot operation is not guaranteed on a free plan. Check the hosting provider's current limits before using it for a real-money bot.

For Render, create a Web Service from this GitHub repository, set the environment variables, and use this start command:

```bash
python main.py
```

The service must use the port provided by Render through the `PORT` environment variable; the app already reads it.

## Admin commands

- `/id` — show your Telegram numeric user ID
- `/addtask Title | https://t.me/examplegroup | 0.01` — add a free task (admin only)
- `/task Title | https://example.com | members` — submit a paid task request
- `/tx REQUEST_ID TXID` — submit a transaction ID for manual review
- `/withdraw 1.00 | 0xYourBEP20Address` — request a withdrawal

The default withdrawal minimum is $1 and at least five qualified referrals are required. Review these rules and all reward values before launch.

## Adsbitvex integration limitations

`webapp.py` contains a browser-side SDK example. The page does not credit a reward when the JavaScript promise resolves. Before paying ad rewards, implement and test a provider-authenticated server-to-server callback or other official server-side verification supported by the provider. Also validate Telegram Web App `initData` server-side before trusting a Telegram user ID. Do not launch real-money ad rewards until these protections are implemented and the provider's terms are reviewed.

## Payment and fraud limitations

A user-submitted transaction ID is not proof of payment by itself. An admin must verify the transfer on the relevant blockchain explorer before approving a task. Referral checks are basic and cannot prevent all fake accounts or device farms. Test thoroughly before handling real funds, and review applicable laws, taxes, and provider policies.

## Pricing defaults

The displayed task-posting price is $4 for up to 2,000 members and $6 for more than 2,000 members. These are configuration defaults only; payment is not automatically verified.

## Render Blueprint (optional)

This repository includes `render.yaml` for Render Blueprint deployment. In Render, create a new Blueprint and select this GitHub repository. Then fill in the required secret environment variables in the Render dashboard. After the service is created, copy its `https://....onrender.com` URL into `PUBLIC_BASE_URL` and save the environment variable. A redeploy may be required after changing it.

Do not assume the free plan is always-on: free web services can spin down after inactivity, which can interrupt Telegram polling. Use an always-on suitable plan for reliable operation.
