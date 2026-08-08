"""
generate_synthetic_data.py
===========================
Builds the labeled training dataset for NUNMAI-MAIL.

WHAT THIS PRODUCES:
  data/synthetic_dataset.csv — see data/README.md for the full schema.

HOW IT WORKS (see data/README.md for the full design rationale):
  1. A small set of SEED TEMPLATES (phishing + legitimate) are defined below
     as Python dicts — each is a category of email (e.g. "KYC expiry scam",
     "genuine quarterly statement") with a subject/body template containing
     {placeholders}.
  2. Each template is expanded into many rows by randomizing names, amounts,
     dates, domains, and — crucially — the HEADER AUTHENTICATION SIGNALS
     (SPF/DKIM/DMARC pass/fail, free-email sender or not) and URL SIGNALS
     (typosquat, shortener, IP-link) that go with it.
  3. Every row gets a full `raw_email_source` (headers + body, .eml-style)
     built by _build_raw_email_source(), so it can be fed DIRECTLY into
     extract_header_features() with no further parsing needed.

Run this file directly to (re)generate the dataset:
    python data\\generate_synthetic_data.py
"""

import csv
import random
from pathlib import Path

# Fixed seed = reproducible dataset. Anyone re-running this gets identical
# output, which matters for debugging and for comparing model runs later.
random.seed(42)

# How many randomized rows to generate PER TEMPLATE. With ~15 templates per
# class and 150 variations each, we land at ~2,250 rows per class (~4,500
# total) — the "Recommended" tier from data/README.md.
VARIATIONS_PER_TEMPLATE = 150

OUTPUT_PATH = Path(__file__).parent / "synthetic_dataset.csv"


# ============================================================
# SECTION 1: RANDOMIZATION POOLS
# Pools of values used to fill in {placeholders} in templates below.
# ============================================================

FIRST_NAMES = [
    "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Ananya", "Rohan", "Kavya",
    "Arjun", "Divya", "Karthik", "Neha", "Suresh", "Pooja", "Manoj", "Ritu",
]
LAST_NAMES = [
    "Sharma", "Verma", "Iyer", "Reddy", "Nair", "Gupta", "Menon", "Rao",
    "Patel", "Joshi", "Pillai", "Kapoor", "Chatterjee", "Desai",
]

# Legitimate financial entities — used for BOTH classes: phishing templates
# impersonate these names while using bad domains/headers; legit templates
# use them with matching, clean domains.
LEGIT_ENTITIES = [
    ("SEBI", "sebi.gov.in"),
    ("Zerodha", "zerodha.com"),
    ("Groww", "groww.in"),
    ("Upstox", "upstox.com"),
    ("ICICI Direct", "icicidirect.com"),
    ("HDFC Securities", "hdfcsec.com"),
    ("NSE", "nseindia.com"),
    ("BSE", "bseindia.com"),
    ("CDSL", "cdslindia.com"),
]

FREE_EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "rediffmail.com"]

SUSPICIOUS_TLDS = ["xyz", "top", "site", "online", "club", "info"]

AMOUNTS_INR = ["₹12,500", "₹48,000", "₹1,25,000", "₹75,300", "₹9,99,000", "₹3,20,500"]

DATES = [
    "07-Jul-2026", "01-Jul-2026", "28-Jun-2026", "15-Jun-2026",
    "30-Jun-2026", "05-Jul-2026",
]


def _random_person():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def _random_victim_email():
    return f"{random.choice(FIRST_NAMES).lower()}.{random.choice(LAST_NAMES).lower()}@example.com"


def _make_typosquat_domain(real_domain: str) -> str:
    """
    Generates a plausible typosquatted version of a real domain by either
    inserting a hyphen, dropping/duplicating a letter, or swapping the TLD
    to a suspicious one — mirrors real attacker behaviour.
    """
    base = real_domain.split(".")[0]
    mutation_type = random.choice(["hyphen", "letter_swap", "suspicious_tld", "extra_word"])

    if mutation_type == "hyphen":
        mutated = base[: len(base) // 2] + "-" + base[len(base) // 2 :]
    elif mutation_type == "letter_swap" and len(base) > 3:
        i = random.randint(1, len(base) - 2)
        mutated = base[:i] + base[i + 1] + base[i] + base[i + 2 :]  # swap two adjacent letters
    elif mutation_type == "extra_word":
        mutated = base + random.choice(["verify", "secure", "kyc", "login", "support"])
    else:
        mutated = base

    tld = random.choice(SUSPICIOUS_TLDS)
    return f"{mutated}.{tld}"


def _random_fake_url(entity_name: str, real_domain: str, style: str) -> str:
    """
    Builds a phishing URL in one of several attacker styles, matching the
    lexical/structural categories from url_features.py's design reference.
    `style` controls which trick is used, so callers can control the mix.
    """
    typo_domain = _make_typosquat_domain(real_domain)
    victim_email = _random_victim_email()

    if style == "typosquat":
        return f"https://{typo_domain}/secure/kyc-update?id={random.randint(1000,9999)}"
    elif style == "ip_address":
        return f"http://{random.randint(10,199)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}/login"
    elif style == "shortener":
        return f"http://bit.ly/{random.choice('abcdefgh')}{random.randint(100,999)}"
    elif style == "email_embedded":
        return f"https://{typo_domain}/verify?email={victim_email}"
    elif style == "at_symbol":
        return f"https://{real_domain}@{typo_domain}/login"
    else:  # "clean" — used for legit emails
        return f"https://www.{real_domain}/account/statements"


def _build_raw_email_source(
    from_name: str,
    from_addr: str,
    subject: str,
    body: str,
    reply_to_addr: str | None = None,
    return_path_addr: str | None = None,
    sender_addr: str | None = None,
    spf: str = "pass",
    dkim: str = "pass",
    dmarc: str = "pass",
    message_id_domain: str | None = None,
    x_mailer: str = "Microsoft Outlook 16.0",
) -> str:
    """
    Assembles a full raw email source (headers + blank line + body),
    formatted exactly like a .eml file / Gmail "Show Original" output —
    ready to be passed directly into extract_header_features().

    Defaults are all "clean/legitimate" (SPF/DKIM/DMARC pass, matching
    Reply-To/Return-Path/Sender, real mail client). Phishing template
    generation overrides specific arguments to inject specific red flags,
    so we control EXACTLY which signal fires per row — this is what makes
    the dataset properly labeled rather than just "randomly bad."
    """
    reply_to_addr = reply_to_addr or from_addr
    return_path_addr = return_path_addr or from_addr
    sender_addr = sender_addr or from_addr
    msg_id_domain = message_id_domain or from_addr.split("@")[-1]
    msg_id = f"<{random.randint(10**9, 10**10-1)}@{msg_id_domain}>"

    return (
        f'From: "{from_name}" <{from_addr}>\n'
        f"To: investor@example.com\n"
        f"Reply-To: {reply_to_addr}\n"
        f"Return-Path: <{return_path_addr}>\n"
        f"Sender: <{sender_addr}>\n"
        f"Subject: {subject}\n"
        f"Message-ID: {msg_id}\n"
        f"X-Mailer: {x_mailer}\n"
        f"Authentication-Results: mx.example.com; spf={spf}; dkim={dkim}; dmarc={dmarc}\n"
        f"Date: Tue, 08 Jul 2026 10:00:00 +0000\n"
        f"\n"
        f"{body}\n"
    )


# ============================================================
# SECTION 2: PHISHING SEED TEMPLATES
# Each template = one attack category. `generate()` returns one randomized
# (subject, body, raw_email_source, notes) tuple per call.
# Add more templates here anytime, following the same shape, to grow
# category diversity without touching the generation loop below.
# ============================================================

def _phish_kyc_expiry(entity_name, real_domain):
    victim = _random_person()
    url = _random_fake_url(entity_name, real_domain, style=random.choice(["typosquat", "ip_address"]))
    subject = f"URGENT: Your {entity_name} KYC Verification Has Expired"
    body = (
        f"Dear {victim},\n\n"
        f"Your KYC with {entity_name} has expired as of {random.choice(DATES)}. "
        f"Your trading account will be suspended within 24 hours unless you verify immediately.\n\n"
        f"Verify now: {url}\n\n"
        f"Failure to act will result in permanent account freeze.\n"
        f"{entity_name} Compliance Team"
    )
    from_domain = _make_typosquat_domain(real_domain)
    from_addr = f"compliance@{from_domain}"
    raw = _build_raw_email_source(
        from_name=f"{entity_name} Compliance Team",
        from_addr=from_addr,
        subject=subject,
        body=body,
        spf="fail", dkim="none", dmarc="fail",
    )
    return subject, body, raw, "Injected: typosquat/IP URL, SPF/DKIM/DMARC fail, spoofed domain"


def _phish_bec_wire_transfer(entity_name, real_domain):
    """AI-enabled BEC style — from a genuinely plausible-looking address,
    relying entirely on TEXT signals (out-of-band excuse, urgency+financial
    combo, over-justification) since headers may actually pass here."""
    victim = _random_person()
    amount = random.choice(AMOUNTS_INR)
    subject = "Quick request before I lose signal"
    body = (
        f"Hi {victim},\n\n"
        f"I hope this email finds you well. I saw your recent LinkedIn post, congratulations "
        f"on the milestone. Speaking of moving things forward quickly, I need you to urgently "
        f"process a payment of {amount} to a new vendor before end of day. "
        f"I'm currently on a plane without cellular service, but the in-flight wifi is letting "
        f"this email through. Please handle this before we land as it is time-sensitive.\n\n"
        f"This is crucial to underscore our commitment to a seamless vendor onboarding process.\n\n"
        f"Thanks,\nCEO"
    )
    # Deliberately mostly-clean headers here: this is the hard case where
    # text signals must do the work since a real account may be compromised.
    spf, dkim, dmarc = random.choice([("pass", "pass", "pass"), ("fail", "none", "fail")])
    from_addr = f"ceo@{real_domain}" if spf == "pass" else f"ceo@{_make_typosquat_domain(real_domain)}"
    raw = _build_raw_email_source(
        from_name="CEO", from_addr=from_addr, subject=subject, body=body,
        spf=spf, dkim=dkim, dmarc=dmarc,
        reply_to_addr=f"ceo.personal@{random.choice(FREE_EMAIL_DOMAINS)}",
    )
    return subject, body, raw, "Injected: BEC pretext, out-of-band excuse, personalization+financial mismatch, Reply-To free-mail"


def _phish_refund_scam(entity_name, real_domain):
    victim = _random_person()
    amount = random.choice(AMOUNTS_INR)
    url = _random_fake_url(entity_name, real_domain, style=random.choice(["shortener", "email_embedded"]))
    subject = f"You are eligible for a {amount} refund from {entity_name}"
    body = (
        f"Dear {victim},\n\n"
        f"Due to a recent regulatory review, you are eligible for a refund of {amount}. "
        f"Claim your refund immediately as this offer expires today: {url}\n\n"
        f"Please provide your bank account number and OTP to process the reimbursement.\n\n"
        f"Regards,\n{entity_name} Refunds Desk"
    )
    from_domain = random.choice(FREE_EMAIL_DOMAINS)
    raw = _build_raw_email_source(
        from_name=f"{entity_name} Refunds Desk",
        from_addr=f"refunds.{entity_name.lower().replace(' ', '')}@{from_domain}",
        subject=subject, body=body,
        spf="fail", dkim="fail", dmarc="fail",
        x_mailer="PHPMailer 6.5",
    )
    return subject, body, raw, "Injected: free-email sender, display-name impersonation, shortener/email-in-URL, urgency+financial combo"


def _phish_exec_impersonation_deepfake_followup(entity_name, real_domain):
    """Text-only pretext referencing a prior 'video call' — ties into the
    NUNMAI-VISION deepfake threat vector; the mail itself is the follow-up
    phishing step after a synthetic-media social-engineering call."""
    victim = _random_person()
    amount = random.choice(AMOUNTS_INR)
    subject = "Following up on our call - please action today"
    body = (
        f"Hi {victim},\n\n"
        f"As discussed on our video call earlier, please go ahead and process the transfer of "
        f"{amount} to the new account we set up. I know this is unusual but given the "
        f"acquisition timeline we cannot use the normal procurement process this time. "
        f"Please action this today and confirm once done. Do not discuss this with anyone else "
        f"on the team until the announcement, given confidentiality reasons.\n\n"
        f"Thanks for your discretion.\nCFO"
    )
    from_domain = _make_typosquat_domain(real_domain)
    raw = _build_raw_email_source(
        from_name="CFO", from_addr=f"cfo@{from_domain}", subject=subject, body=body,
        spf="fail", dkim="none", dmarc="fail",
    )
    return subject, body, raw, "Injected: bypasses-procedure pretext, secrecy/isolation request, spoofed domain"


def _phish_dividend_ipo_scam(entity_name, real_domain):
    victim = _random_person()
    amount = random.choice(AMOUNTS_INR)
    url = _random_fake_url(entity_name, real_domain, style="typosquat")
    subject = f"Congratulations! Your IPO allotment of {amount} is confirmed"
    body = (
        f"Dear {victim},\n\n"
        f"Congratulations! You have been allotted shares worth {amount} in the latest IPO. "
        f"To claim your allotment, complete verification here: {url}\n\n"
        f"This link will expire in 2 hours. Act now to avoid losing your allotment.\n\n"
        f"{entity_name} Allotment Team"
    )
    from_domain = _make_typosquat_domain(real_domain)
    raw = _build_raw_email_source(
        from_name=f"{entity_name} Allotment Team", from_addr=f"allotment@{from_domain}",
        subject=subject, body=body, spf="softfail", dkim="fail", dmarc="fail",
    )
    return subject, body, raw, "Injected: typosquat URL, urgency, softfail/fail auth"

def _phish_sms_style_otp(entity_name, real_domain):
    """Deliberately VERY SHORT — mirrors real SMS-style phishing, which is
    often just one line. Breaks the 'phishing = long' shortcut."""
    url = _random_fake_url(entity_name, real_domain, style="shortener")
    subject = "Account Alert"
    body = f"Your {entity_name} account is locked. Verify now: {url}"
    from_domain = random.choice(FREE_EMAIL_DOMAINS)
    raw = _build_raw_email_source(
        from_name=entity_name, from_addr=f"alert@{from_domain}",
        subject=subject, body=body, spf="fail", dkim="none", dmarc="fail",
    )
    return subject, body, raw, "Injected: very short SMS-style scam, shortener URL, free-email sender"


def _phish_short_account_locked(entity_name, real_domain):
    """Another short one — one-line urgency + link, no elaborate narrative."""
    url = _random_fake_url(entity_name, real_domain, style="typosquat")
    subject = "Action Required"
    body = f"Suspicious login detected. Confirm it was you or your account will be suspended: {url}"
    from_domain = _make_typosquat_domain(real_domain)
    raw = _build_raw_email_source(
        from_name="Security Team", from_addr=f"security@{from_domain}",
        subject=subject, body=body, spf="softfail", dkim="fail", dmarc="fail",
    )
    return subject, body, raw, "Injected: short one-liner, typosquat URL, softfail/fail auth"


def _phish_elaborate_sebi_penalty(entity_name, real_domain):
    """Deliberately LONG and formal — mimics a legitimate legal/regulatory
    notice in length and tone, to force the model past surface-length cues."""
    victim = _random_person()
    amount = random.choice(AMOUNTS_INR)
    url = _random_fake_url(entity_name, real_domain, style="typosquat")
    subject = f"Formal Notice: Regulatory Penalty Assessment - Case Ref {random.randint(100000,999999)}"
    body = (
        f"Dear {victim},\n\n"
        f"This is a formal notice issued under the applicable securities regulations regarding "
        f"discrepancies identified in your trading account during our routine compliance audit "
        f"conducted for the period ending {random.choice(DATES)}. Our review has identified "
        f"certain irregularities that require your immediate attention and response.\n\n"
        f"As per our findings, a provisional penalty assessment of {amount} has been levied "
        f"against your account pending your response. This assessment has been made in "
        f"accordance with standard regulatory procedures and is subject to review upon "
        f"submission of the required documentation.\n\n"
        f"To avoid escalation of this matter and potential suspension of your trading "
        f"privileges, you are required to complete the verification process and submit your "
        f"response within 48 hours of receipt of this notice. Please note that failure to "
        f"respond within the stipulated timeframe may result in further regulatory action "
        f"being taken against your account, including but not limited to account freeze and "
        f"referral to the appropriate enforcement division.\n\n"
        f"Please complete your verification and review the full details of this assessment "
        f"at the following secure portal: {url}\n\n"
        f"We appreciate your prompt attention to this matter and thank you for your continued "
        f"cooperation with our compliance procedures.\n\n"
        f"Regards,\nRegulatory Compliance Division\n{entity_name}"
    )
    from_domain = _make_typosquat_domain(real_domain)
    raw = _build_raw_email_source(
        from_name="Regulatory Compliance Division", from_addr=f"compliance@{from_domain}",
        subject=subject, body=body, spf="fail", dkim="fail", dmarc="fail",
    )
    return subject, body, raw, "Injected: LONG formal-sounding scam, typosquat URL, all-auth-fail"


def _phish_investment_tip_scam(entity_name, real_domain):
    """Long, elaborate fake insider-tip / guaranteed-returns scam."""
    victim = _random_person()
    url = _random_fake_url(entity_name, real_domain, style="typosquat")
    subject = "Exclusive Investment Opportunity - Limited Slots Available"
    body = (
        f"Dear {victim},\n\n"
        f"We are reaching out to a select group of high-net-worth investors regarding an "
        f"exclusive pre-IPO investment opportunity that is not yet available to the general "
        f"public. Based on your trading history and portfolio profile, our advisory team has "
        f"identified you as an ideal candidate for this limited allocation.\n\n"
        f"This opportunity offers guaranteed returns significantly above market average, "
        f"backed by insider access to upcoming listing information. Due to regulatory "
        f"sensitivities around this opportunity, we are only able to share full details "
        f"through our secure investor portal, and slots are strictly limited to the first "
        f"50 respondents.\n\n"
        f"To secure your allocation, please complete your investor verification and initial "
        f"deposit through the link below within the next 24 hours: {url}\n\n"
        f"We look forward to welcoming you as one of our exclusive portfolio partners.\n\n"
        f"Warm regards,\nInvestment Advisory Team"
    )
    from_domain = random.choice(FREE_EMAIL_DOMAINS)
    raw = _build_raw_email_source(
        from_name="Investment Advisory Team", from_addr=f"advisory@{from_domain}",
        subject=subject, body=body, spf="fail", dkim="none", dmarc="fail",
    )
    return subject, body, raw, "Injected: LONG guaranteed-returns scam, free-email sender, urgency+exclusivity pretext"


def _phish_short_password_reset(entity_name, real_domain):
    """Short, mimics a legit password-reset email almost exactly, EXCEPT
    the link/domain is bad — tests whether the model relies on link/domain
    signals rather than tone."""
    url = _random_fake_url(entity_name, real_domain, style="typosquat")
    subject = "Password Reset Requested"
    body = f"A password reset was requested for your account. Click here to reset: {url}. If you did not request this, ignore this email."
    from_domain = _make_typosquat_domain(real_domain)
    raw = _build_raw_email_source(
        from_name=entity_name, from_addr=f"noreply@{from_domain}",
        subject=subject, body=body, spf="fail", dkim="none", dmarc="fail",
    )
    return subject, body, raw, "Injected: short, mimics legit password-reset tone, but typosquat domain + auth fail"


def _phish_medium_job_scam(entity_name, real_domain):
    """Medium-length job/finance-recruitment-flavoured scam."""
    victim = _random_person()
    amount = random.choice(AMOUNTS_INR)
    url = _random_fake_url(entity_name, real_domain, style="email_embedded")
    subject = "Remote Trading Analyst Opportunity - Immediate Start"
    body = (
        f"Hi {victim},\n\n"
        f"We came across your profile and think you'd be a great fit for a remote trading "
        f"analyst role with flexible hours and a starting package of {amount} per month. "
        f"No prior experience required, full training provided.\n\n"
        f"To proceed with your application, please complete the registration form here: {url}\n\n"
        f"Spots are filling quickly, so please apply today.\n\n"
        f"HR Team"
    )
    from_domain = random.choice(FREE_EMAIL_DOMAINS)
    raw = _build_raw_email_source(
        from_name="HR Team", from_addr=f"hr.hiring@{from_domain}",
        subject=subject, body=body, spf="fail", dkim="fail", dmarc="none",
    )
    return subject, body, raw, "Injected: medium-length job scam, email-embedded URL, free-email sender"


def _phish_short_dividend_alert(entity_name, real_domain):
    """Very short dividend-alert scam."""
    amount = random.choice(AMOUNTS_INR)
    url = _random_fake_url(entity_name, real_domain, style="ip_address")
    subject = f"Dividend of {amount} pending"
    body = f"A dividend payout of {amount} is pending release. Claim before it expires: {url}"
    from_domain = _make_typosquat_domain(real_domain)
    raw = _build_raw_email_source(
        from_name=entity_name, from_addr=f"payouts@{from_domain}",
        subject=subject, body=body, spf="softfail", dkim="none", dmarc="fail",
    )
    return subject, body, raw, "Injected: very short, IP-address URL, softfail/none auth"

def _legit_short_otp(entity_name, real_domain):
    """Very short — genuine OTP messages are always terse."""
    subject = "Your OTP Code"
    body = f"Your OTP for login is {random.randint(100000,999999)}. Valid for 10 minutes. Do not share this with anyone."
    raw = _build_raw_email_source(
        from_name=entity_name, from_addr=f"noreply@{real_domain}",
        subject=subject, body=body, spf="pass", dkim="pass", dmarc="pass",
    )
    return subject, body, raw, "Clean: very short genuine OTP message, matching domain, auth pass"


def _legit_short_trade_alert(entity_name, real_domain):
    """Short genuine trade alert."""
    amount = random.choice(AMOUNTS_INR)
    subject = "Order Alert"
    body = f"Your limit order for {amount} has been placed successfully. Track it in the app."
    raw = _build_raw_email_source(
        from_name=entity_name, from_addr=f"alerts@{real_domain}",
        subject=subject, body=body, spf="pass", dkim="pass", dmarc="pass",
    )
    return subject, body, raw, "Clean: short genuine order alert, matching domain, auth pass"


def _legit_long_policy_update(entity_name, real_domain):
    """Deliberately LONG — genuine T&C/policy update emails are often
    lengthy and formal, exactly like some of our long phishing templates."""
    victim = _random_person()
    subject = "Important Update to Our Terms of Service"
    body = (
        f"Dear {victim},\n\n"
        f"We are writing to inform you of upcoming changes to our Terms of Service and "
        f"Privacy Policy, effective {random.choice(DATES)}. These changes reflect updates "
        f"to applicable regulations and improvements to how we handle your account "
        f"information and trading activity.\n\n"
        f"Key changes include updated brokerage fee disclosures, revised data retention "
        f"periods in line with regulatory requirements, and clarified procedures for "
        f"dispute resolution. A full summary of changes is available in your account "
        f"dashboard under Settings > Legal.\n\n"
        f"We encourage you to review these changes at your convenience. Continued use of "
        f"our services after the effective date constitutes acceptance of the updated "
        f"terms. If you have any questions or concerns regarding these updates, our support "
        f"team is available through the in-app chat or by raising a ticket through your "
        f"dashboard.\n\n"
        f"We remain committed to transparency and to keeping you informed of any material "
        f"changes that may affect your account or trading experience.\n\n"
        f"Thank you for continuing to trust us with your investments.\n\n"
        f"Regards,\nLegal & Compliance Team\n{entity_name}"
    )
    raw = _build_raw_email_source(
        from_name="Legal & Compliance Team", from_addr=f"legal@{real_domain}",
        subject=subject, body=body, spf="pass", dkim="pass", dmarc="pass",
    )
    return subject, body, raw, "Clean: LONG genuine policy update, matching domain, auth pass"


def _legit_long_research_report(entity_name, real_domain):
    """Deliberately LONG genuine research/market commentary email."""
    victim = _random_person()
    url = _random_fake_url(entity_name, real_domain, style="clean")
    subject = "Monthly Market Outlook and Portfolio Insights"
    body = (
        f"Dear {victim},\n\n"
        f"Here is your monthly market outlook covering key macroeconomic developments, "
        f"sector performance, and portfolio recommendations for the period ahead.\n\n"
        f"Equity markets remained range-bound through the month as investors weighed "
        f"mixed earnings signals against ongoing global rate uncertainty. Large-cap IT and "
        f"pharma stocks outperformed, while mid-cap manufacturing names saw some profit "
        f"booking after a strong preceding quarter. Foreign institutional flows turned "
        f"marginally positive, while domestic mutual fund inflows continued their steady "
        f"upward trend, providing a stable floor for the broader market.\n\n"
        f"On the fixed income side, bond yields eased slightly following commentary from "
        f"the central bank suggesting a pause in the current policy cycle. We continue to "
        f"recommend a balanced allocation across large-cap equities, high-quality debt "
        f"instruments, and a modest allocation to gold as a hedge against global "
        f"volatility.\n\n"
        f"For a detailed sector-by-sector breakdown and updated model portfolio "
        f"allocations, please refer to the full report: {url}\n\n"
        f"As always, please reach out to your relationship manager if you'd like to "
        f"discuss how these insights apply to your specific portfolio.\n\n"
        f"Best regards,\nResearch Desk\n{entity_name}"
    )
    raw = _build_raw_email_source(
        from_name="Research Desk", from_addr=f"research@{real_domain}",
        subject=subject, body=body, spf="pass", dkim="pass", dmarc="pass",
    )
    return subject, body, raw, "Clean: LONG genuine research report, matching domain, auth pass"


def _legit_medium_password_reset(entity_name, real_domain):
    """Genuine password reset — medium length, matches the phishing
    password-reset template in structure/tone, but with clean domain/auth."""
    url = _random_fake_url(entity_name, real_domain, style="clean")
    subject = "Password Reset Requested"
    body = (
        f"A password reset was requested for your account. If this was you, click below "
        f"to reset your password: {url}\n\n"
        f"This link will expire in 30 minutes. If you did not request this change, no "
        f"action is needed and your password will remain unchanged."
    )
    raw = _build_raw_email_source(
        from_name=entity_name, from_addr=f"noreply@{real_domain}",
        subject=subject, body=body, spf="pass", dkim="pass", dmarc="pass",
    )
    return subject, body, raw, "Clean: genuine password reset, matching domain, auth pass - mirrors phishing template in tone to test model relies on domain/auth not wording"


def _legit_medium_account_statement(entity_name, real_domain):
    """Medium-length genuine account statement notification."""
    victim = _random_person()
    url = _random_fake_url(entity_name, real_domain, style="clean")
    subject = "Your Monthly Account Statement"
    body = (
        f"Dear {victim},\n\n"
        f"Your account statement for {random.choice(DATES)} is now available for download. "
        f"This statement includes a summary of all transactions, holdings, and applicable "
        f"charges for the period.\n\n"
        f"View and download your statement here: {url}\n\n"
        f"Please retain this for your records. Contact support if you notice any discrepancies.\n\n"
        f"Regards,\n{entity_name} Accounts Team"
    )
    raw = _build_raw_email_source(
        from_name=f"{entity_name} Accounts Team", from_addr=f"accounts@{real_domain}",
        subject=subject, body=body, spf="pass", dkim="pass", dmarc="pass",
    )
    return subject, body, raw, "Clean: medium genuine statement notice, matching domain, auth pass"


def _legit_long_onboarding_welcome(entity_name, real_domain):
    """Long genuine welcome/onboarding email."""
    victim = _random_person()
    url = _random_fake_url(entity_name, real_domain, style="clean")
    subject = f"Welcome to {entity_name} - Getting Started"
    body = (
        f"Dear {victim},\n\n"
        f"Welcome aboard! We're glad to have you as part of the {entity_name} community. "
        f"This email will walk you through a few quick steps to get your account fully set "
        f"up and ready for trading.\n\n"
        f"First, please complete your KYC verification if you haven't already, which "
        f"typically takes just a few minutes and requires your PAN and a valid address "
        f"proof. Once verified, you'll be able to add funds to your trading account through "
        f"any of our supported payment methods, including UPI, net banking, and NEFT/RTGS "
        f"transfers.\n\n"
        f"We also recommend exploring our education center, where you'll find beginner "
        f"guides on order types, margin trading, and portfolio diversification, as well as "
        f"webinars hosted by our in-house research analysts. If you're migrating from "
        f"another broker, our support team can help guide you through the account transfer "
        f"process.\n\n"
        f"For any questions along the way, our support team is available via in-app chat, "
        f"or you can browse our detailed help center at: {url}\n\n"
        f"We're excited to support you on your investing journey.\n\n"
        f"Warm regards,\nThe {entity_name} Team"
    )
    raw = _build_raw_email_source(
        from_name=f"{entity_name} Team", from_addr=f"welcome@{real_domain}",
        subject=subject, body=body, spf="pass", dkim="pass", dmarc="pass",
    )
    return subject, body, raw, "Clean: LONG genuine onboarding email, matching domain, auth pass"


def _phish_sebi_show_cause_notice(entity_name, real_domain):
    """SEBI-specific: Urgent Show Cause Notice phishing scam."""
    victim = _random_person()
    url = _random_fake_url("SEBI", "sebi.gov.in", style="typosquat")
    subject = f"URGENT: SEBI Show Cause Notice - Account Suspension"
    body = (
        f"Dear {victim},\n\n"
        f"This is a formal Show Cause Notice issued by the Securities and Exchange Board of India (SEBI). "
        f"We have detected illegal trading activities in your associated demat account.\n\n"
        f"You are required to submit an explanation within 24 hours to prevent immediate freezing "
        f"of all your trading accounts and assets. Failure to comply will result in an immediate penalty of {random.choice(AMOUNTS_INR)}.\n\n"
        f"Click here to view the evidence and submit your response: {url}\n\n"
        f"SEBI Enforcement Directorate"
    )
    from_domain = _make_typosquat_domain("sebi.gov.in")
    raw = _build_raw_email_source(
        from_name="SEBI Enforcement Directorate", from_addr=f"enforcement@{from_domain}",
        subject=subject, body=body, spf="fail", dkim="fail", dmarc="fail",
    )
    return subject, body, raw, "Injected: SEBI show cause notice, urgency+financial combo, typosquat URL"


def _phish_sebi_investor_grievance(entity_name, real_domain):
    """SEBI-specific: Fake Investor Grievance Redressal phishing scam."""
    victim = _random_person()
    url = _random_fake_url("SEBI", "sebi.gov.in", style="ip_address")
    subject = "SEBI SCORES - Action Required on your Grievance"
    body = (
        f"Dear {victim},\n\n"
        f"Your investor grievance filed with SEBI SCORES requires additional verification "
        f"before we can process your refund of {random.choice(AMOUNTS_INR)}.\n\n"
        f"Please log in to the secure SEBI portal via the IP provided below to verify your bank account details.\n\n"
        f"Login: {url}\n\n"
        f"Note: This link is valid for 48 hours. If verification is not completed, your grievance will be closed.\n\n"
        f"Regards,\nSEBI Investor Grievance Cell"
    )
    from_domain = random.choice(FREE_EMAIL_DOMAINS)
    raw = _build_raw_email_source(
        from_name="SEBI Investor Grievance Cell", from_addr=f"sebi.scores.redressal@{from_domain}",
        subject=subject, body=body, spf="fail", dkim="none", dmarc="fail",
    )
    return subject, body, raw, "Injected: SEBI grievance refund scam, IP URL, free-email sender"

PHISHING_TEMPLATES = {
    "phish_kyc_expiry": _phish_kyc_expiry,
    "phish_bec_wire_transfer": _phish_bec_wire_transfer,
    "phish_refund_scam": _phish_refund_scam,
    "phish_exec_impersonation": _phish_exec_impersonation_deepfake_followup,
    "phish_dividend_ipo_scam": _phish_dividend_ipo_scam,
    "phish_sms_style_otp": _phish_sms_style_otp,
    "phish_short_account_locked": _phish_short_account_locked,
    "phish_elaborate_sebi_penalty": _phish_elaborate_sebi_penalty,
    "phish_investment_tip_scam": _phish_investment_tip_scam,
    "phish_short_password_reset": _phish_short_password_reset,
    "phish_medium_job_scam": _phish_medium_job_scam,
    "phish_short_dividend_alert": _phish_short_dividend_alert,
    "phish_sebi_show_cause_notice": _phish_sebi_show_cause_notice,
    "phish_sebi_investor_grievance": _phish_sebi_investor_grievance,
}


# ============================================================
# SECTION 3: LEGITIMATE SEED TEMPLATES
# ============================================================

def _legit_quarterly_statement(entity_name, real_domain):
    victim = _random_person()
    url = _random_fake_url(entity_name, real_domain, style="clean")
    subject = "Your Quarterly Statement is Ready"
    body = (
        f"Dear {victim},\n\n"
        f"Your quarterly account statement for the period ending {random.choice(DATES)} is now "
        f"available in your dashboard.\n\n"
        f"View statement: {url}\n\n"
        f"If you have any questions, contact our support team through the app.\n\n"
        f"Regards,\n{entity_name} Support"
    )
    raw = _build_raw_email_source(
        from_name=f"{entity_name} Support", from_addr=f"support@{real_domain}",
        subject=subject, body=body, spf="pass", dkim="pass", dmarc="pass",
    )
    return subject, body, raw, "Clean: matching domain, all auth pass, no suspicious URL"


def _legit_kyc_reminder(entity_name, real_domain):
    victim = _random_person()
    url = _random_fake_url(entity_name, real_domain, style="clean")
    subject = "Reminder: Annual KYC Update"
    body = (
        f"Dear {victim},\n\n"
        f"As part of routine compliance, please update your KYC details at your convenience "
        f"before {random.choice(DATES)}. There is no immediate action required if your details "
        f"are already current.\n\n"
        f"Update here: {url}\n\n"
        f"Thank you,\n{entity_name} Compliance"
    )
    raw = _build_raw_email_source(
        from_name=f"{entity_name} Compliance", from_addr=f"compliance@{real_domain}",
        subject=subject, body=body, spf="pass", dkim="pass", dmarc="pass",
    )
    return subject, body, raw, "Clean: genuine non-urgent KYC reminder, matching domain, auth pass"


def _legit_trade_confirmation(entity_name, real_domain):
    victim = _random_person()
    amount = random.choice(AMOUNTS_INR)
    subject = "Trade Confirmation - Order Executed"
    body = (
        f"Dear {victim},\n\n"
        f"This confirms your order for {amount} has been executed successfully. "
        f"Contract note will be sent separately within 24 hours as per regulatory requirement.\n\n"
        f"Regards,\n{entity_name} Trade Desk"
    )
    raw = _build_raw_email_source(
        from_name=f"{entity_name} Trade Desk", from_addr=f"tradedesk@{real_domain}",
        subject=subject, body=body, spf="pass", dkim="pass", dmarc="pass",
    )
    return subject, body, raw, "Clean: routine transactional email, no links, auth pass"


def _legit_newsletter(entity_name, real_domain):
    victim = _random_person()
    url = _random_fake_url(entity_name, real_domain, style="clean")
    subject = "This Week in Markets"
    body = (
        f"Hi {victim},\n\n"
        f"Here's your weekly market roundup: Nifty closed flat, IT stocks rallied on strong "
        f"earnings, and RBI policy meeting is scheduled next week.\n\n"
        f"Read the full report: {url}\n\n"
        f"{entity_name} Research Team"
    )
    raw = _build_raw_email_source(
        from_name=f"{entity_name} Research", from_addr=f"research@{real_domain}",
        subject=subject, body=body, spf="pass", dkim="pass", dmarc="pass",
    )
    return subject, body, raw, "Clean: informational newsletter, matching domain, auth pass"


def _legit_internal_colleague(entity_name, real_domain):
    """Deliberately terse, human, imperfect writing — the 'too perfect
    problem' contrast case for text_features.py's burstiness/trope checks."""
    victim = _random_person()
    subject = "invoice"
    body = (
        f"hey {victim.split()[0]}, saw the invoice from the vendor. approved, go ahead and pay it. "
        f"also loop in the team on the numbers when you get a sec. thx"
    )
    raw = _build_raw_email_source(
        from_name="Manager", from_addr=f"manager@{real_domain}",
        subject=subject, body=body, spf="pass", dkim="pass", dmarc="pass",
        x_mailer="iPhone Mail",
    )
    return subject, body, raw, "Clean: terse human writing, high burstiness expected, no trope words"


LEGIT_TEMPLATES = {
    "legit_quarterly_statement": _legit_quarterly_statement,
    "legit_kyc_reminder": _legit_kyc_reminder,
    "legit_trade_confirmation": _legit_trade_confirmation,
    "legit_newsletter": _legit_newsletter,
    "legit_internal_colleague": _legit_internal_colleague,
    "legit_short_otp": _legit_short_otp,
    "legit_short_trade_alert": _legit_short_trade_alert,
    "legit_long_policy_update": _legit_long_policy_update,
    "legit_long_research_report": _legit_long_research_report,
    "legit_medium_password_reset": _legit_medium_password_reset,
    "legit_medium_account_statement": _legit_medium_account_statement,
    "legit_long_onboarding_welcome": _legit_long_onboarding_welcome,
}


# ============================================================
# SECTION 4: GENERATION LOOP
# ============================================================

def generate_dataset() -> list[dict]:
    """Expands every template (phishing + legit) into VARIATIONS_PER_TEMPLATE
    randomized rows each, returning the full list of row-dicts matching the
    schema documented in data/README.md."""
    rows = []
    row_id = 1

    def _run_templates(template_dict: dict, label: int, category_prefix: str):
        nonlocal row_id
        for template_id, template_fn in template_dict.items():
            for _ in range(VARIATIONS_PER_TEMPLATE):
                entity_name, real_domain = random.choice(LEGIT_ENTITIES)
                subject, body, raw, notes = template_fn(entity_name, real_domain)
                rows.append({
                    "id": row_id,
                    "label": label,
                    "template_id": template_id,
                    "category": f"{category_prefix}: {template_id.replace('_', ' ').title()}",
                    "subject": subject,
                    "body_text": body,
                    "raw_email_source": raw,
                    "notes": notes,
                })
                row_id += 1

    _run_templates(PHISHING_TEMPLATES, label=1, category_prefix="Phishing")
    _run_templates(LEGIT_TEMPLATES, label=0, category_prefix="Legitimate")

    random.shuffle(rows)  # avoid all-phishing-then-all-legit ordering in the CSV
    return rows


def main():
    rows = generate_dataset()
    fieldnames = ["id", "label", "template_id", "category", "subject", "body_text", "raw_email_source", "notes"]

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    num_phish = sum(1 for r in rows if r["label"] == 1)
    num_legit = sum(1 for r in rows if r["label"] == 0)
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")
    print(f"  Phishing: {num_phish}")
    print(f"  Legitimate: {num_legit}")
    print(f"  Templates used: {len(PHISHING_TEMPLATES)} phishing, {len(LEGIT_TEMPLATES)} legit")


if __name__ == "__main__":
    main()