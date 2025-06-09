# Dice Auto Apply

This project automates job applications on Dice.com using Selenium. It logs into your account, navigates through search results, and attempts to apply to jobs using the "Easy Apply" feature.

## Setup
1. Create a `.env` file with your Dice credentials:
   ```
   EMAIL=you@example.com
   PASSWORD=yourpassword
   ```
2. Adjust `config.json` with your search URL and limits.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running
```bash
python dice_autoapply.py
```

Applied and failed applications are logged to `applied_log.json` and `failed_log.json` respectively. Open `index.html` in a browser to view them.
