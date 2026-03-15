"""
סורק עבודות צילום ועריכה – Apify + Streamlit
"""

import streamlit as st
import pandas as pd
import requests
import json
import re
import time
import os
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────
# .env helpers
# ─────────────────────────────────────────────
ENV_FILE = Path(".env")

def load_env_key() -> str:
    """טען Apify token מקובץ .env אם קיים"""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("APIFY_TOKEN="):
                return line.split("=", 1)[1].strip()
    return ""

def save_env_key(token: str):
    """שמור Apify token לקובץ .env"""
    lines = []
    if ENV_FILE.exists():
        lines = [l for l in ENV_FILE.read_text(encoding="utf-8").splitlines()
                 if not l.startswith("APIFY_TOKEN=")]
    lines.append(f"APIFY_TOKEN={token}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

def delete_env_key():
    """מחק את הטוקן מהקובץ"""
    if ENV_FILE.exists():
        lines = [l for l in ENV_FILE.read_text(encoding="utf-8").splitlines()
                 if not l.startswith("APIFY_TOKEN=")]
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

# ─────────────────────────────────────────────
# קבועים
# ─────────────────────────────────────────────
MY_INFO = {
    "name": "אומר",
    "phone": "058-743-2288",
    "website": "omerphotos.com",
    "email": "omer7411@gmail.com",
}

PHOTO_KEYWORDS  = ["צלם", "צילום", "photographer", "photography", "צלמת", "פוטוגרף", "צילומי"]
EDIT_KEYWORDS   = ["עורך וידאו", "עריכת וידאו", "עריכה", "מונטאז'", "video editor", "video editing", "עורכת וידאו"]
REMOTE_KEYWORDS = ["מרחוק", "מהבית", "remote", "online", "פרילנס", "freelance", "עבודה מהבית"]

DEFAULT_GROUPS = [
    "https://www.facebook.com/groups/photographersisrael",
    "https://www.facebook.com/groups/videoeditors.il",
    "https://www.facebook.com/groups/freelancers.israel",
    "https://www.facebook.com/groups/cinemaproduction.israel",
    "https://www.facebook.com/groups/production.israel",
]

APIFY_ACTOR = "apify/facebook-groups-scraper"

# ─────────────────────────────────────────────
# לוגיקת סינון ותגובות
# ─────────────────────────────────────────────

def classify_post(text):
    t = text.lower()
    if any(k.lower() in t for k in PHOTO_KEYWORDS):
        return "📷 צילום"
    if any(k.lower() in t for k in EDIT_KEYWORDS):
        is_remote = any(k.lower() in t for k in REMOTE_KEYWORDS)
        return "🎬 עריכה (ריילנס)" if is_remote else "🎬 עריכה"
    return None


def extract_contact(text):
    phone = re.search(r'0[5-9][0-9]-?\d{7}|\+972-?[5-9][0-9]-?\d{7}', text)
    if phone:
        return phone.group(0)
    email = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    if email:
        return email.group(0)
    return "—"


def build_reply(job_type, poster):
    greeting = f"היי {poster}! 👋" if poster and poster != "לא ידוע" else "היי! 👋"
    if "צילום" in job_type:
        role = "צלם מקצועי עם ניסיון רב בצילומי אירועים, מוצרים ותוכן דיגיטלי"
    else:
        role = "עורך וידאו עם ניסיון בריילס, רילז, סרטי קידום ותוכן דיגיטלי"
    remote = "\n✅ עובד גם מרחוק – נוח לכל לקוח!" if "ריילנס" in job_type else ""

    return (
        f"{greeting}\n\n"
        f"ראיתי את הפוסט ואשמח לעזור 🙂\n"
        f"אני {MY_INFO['name']} – {role}.{remote}\n\n"
        f"📞 {MY_INFO['phone']}\n"
        f"🌐 {MY_INFO['website']}\n"
        f"📧 {MY_INFO['email']}\n\n"
        f"מוזמן/ת לפנות ונדבר על הפרויקט!"
    )

# ─────────────────────────────────────────────
# Apify
# ─────────────────────────────────────────────

def run_apify_scraper(api_key, group_urls, max_posts):
    run_url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/runs?token={api_key}"
    payload = {
        "startUrls": [{"url": u} for u in group_urls],
        "maxPosts": max_posts,
        "includeComments": False,
        "maxComments": 0,
    }

    with st.spinner("🚀 שולח בקשה ל-Apify..."):
        resp = requests.post(run_url, json=payload, timeout=30)

    if resp.status_code not in (200, 201):
        st.error(f"❌ Apify החזיר שגיאה {resp.status_code}: {resp.text[:300]}")
        return []

    data = resp.json()["data"]
    run_id = data["id"]
    dataset_id = data["defaultDatasetId"]
    st.info(f"✅ Run ID: `{run_id}` – ממתין לסיום...")

    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={api_key}"
    bar = st.progress(0, text="סורק קבוצות...")
    elapsed = 0
    max_wait = 300

    while elapsed < max_wait:
        time.sleep(8)
        elapsed += 8
        run_status = requests.get(status_url, timeout=15).json()["data"]["status"]
        pct = min(int(elapsed / max_wait * 100), 95)
        bar.progress(pct, text=f"סטטוס: {run_status} ({elapsed}s)...")

        if run_status == "SUCCEEDED":
            bar.progress(100, text="✅ הסריקה הושלמה!")
            break
        if run_status in ("FAILED", "ABORTED", "TIMED-OUT"):
            st.error(f"❌ הסריקה נכשלה: {run_status}")
            return []

    data_url = (
        f"https://api.apify.com/v2/datasets/{dataset_id}/items"
        f"?token={api_key}&format=json&limit=1000"
    )
    items = requests.get(data_url, timeout=30).json()
    return items if isinstance(items, list) else []


def process_items(raw_items):
    results = []
    for item in raw_items:
        text = (
            item.get("text")
            or item.get("message")
            or item.get("postText")
            or ""
        )
        if not text or len(text) < 20:
            continue

        job_type = classify_post(text)
        if not job_type:
            continue

        poster = (
            item.get("authorName")
            or item.get("ownerName")
            or (item.get("user") or {}).get("name", "")
            or "לא ידוע"
        )
        link    = item.get("url") or item.get("postUrl") or item.get("link") or "—"
        group   = item.get("groupName") or item.get("pageTitle") or "—"
        contact = extract_contact(text)
        reply   = build_reply(job_type, poster)

        results.append({
            "שם המפרסם":   poster,
            "סוג עבודה":   job_type,
            "פרטי קשר":    contact,
            "קבוצה":       group,
            "תוכן הפוסט":  text[:350] + ("…" if len(text) > 350 else ""),
            "הצעת תגובה":  reply,
            "קישור לפוסט": link,
        })
    return results

# ─────────────────────────────────────────────
# ממשק Streamlit
# ─────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="סורק עבודות פייסבוק",
        page_icon="📷",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Heebo', sans-serif; direction: rtl; }
    .stButton > button { border-radius: 10px; font-weight: 600; }
    .reply-card {
        background: #f8faff;
        border-right: 4px solid #1877F2;
        padding: 14px 18px;
        border-radius: 10px;
        white-space: pre-wrap;
        font-size: 0.9rem;
        line-height: 1.7;
        direction: rtl;
        color: #1c1c1c;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("## 📷 סורק עבודות צילום ועריכה")
    st.caption("מבוסס Apify – סריקת פייסבוק בענן, ללא Selenium")
    st.divider()

    # ─── סרגל צד ───
    with st.sidebar:
        st.header("🔑 Apify")

        # טען טוקן שמור אם קיים
        saved_token = load_env_key()
        token_saved = bool(saved_token)

        apify_key = st.text_input(
            "API Key",
            value=saved_token,
            type="password",
            help="apify.com → Settings → Integrations → Personal API token",
        )
        st.markdown("[📎 קבל API Key חינמי](https://console.apify.com/account/integrations)")

        col_save, col_del = st.columns(2)
        with col_save:
            if st.button("💾 שמור טוקן", use_container_width=True, disabled=not apify_key):
                save_env_key(apify_key)
                st.success("✅ נשמר!")
        with col_del:
            if st.button("🗑️ מחק טוקן", use_container_width=True, disabled=not token_saved):
                delete_env_key()
                st.warning("טוקן נמחק")
                st.rerun()

        if token_saved:
            st.caption("🟢 טוקן שמור נטען אוטומטית")

        st.divider()
        st.header("👤 הפרטים שלי")
        MY_INFO["name"]    = st.text_input("שם",    value=MY_INFO["name"])
        MY_INFO["phone"]   = st.text_input("טלפון", value=MY_INFO["phone"])
        MY_INFO["website"] = st.text_input("אתר",   value=MY_INFO["website"])
        MY_INFO["email"]   = st.text_input("מייל",  value=MY_INFO["email"])

        st.divider()
        st.header("⚙️ סריקה")
        max_posts = st.slider("פוסטים מקסימום לקבוצה", 10, 100, 30)

        st.header("📋 קבוצות")
        groups_text = st.text_area(
            "קישורים (שורה לכל קישור)",
            value="\n".join(DEFAULT_GROUPS),
            height=180,
        )

    # ─── טאבים ───
    tab_scan, tab_results, tab_help = st.tabs(["🚀 סריקה", "📊 תוצאות", "ℹ️ עזרה"])

    # ══ סריקה ══
    with tab_scan:
        group_urls = [u.strip() for u in groups_text.splitlines() if u.strip().startswith("http")]

        c1, c2, c3 = st.columns(3)
        c1.metric("קבוצות", len(group_urls))
        c2.metric("פוסטים מקסימום", max_posts * len(group_urls))
        c3.metric("סוג עבודה", "צילום + עריכה")

        st.info("האפליקציה תסרוק את הקבוצות דרך Apify, תסנן מודעות רלוונטיות ותכין תגובות מוכנות.")

        if st.button("▶️ התחל סריקה", type="primary", use_container_width=True):
            if not apify_key:
                st.error("❌ יש להזין Apify API Key בסרגל הצד")
                st.stop()
            if not group_urls:
                st.error("❌ יש להוסיף לפחות קישור קבוצה אחד")
                st.stop()

            raw     = run_apify_scraper(apify_key, group_urls, max_posts)
            results = process_items(raw) if raw else []

            if results:
                st.session_state["results"]   = results
                st.session_state["scan_time"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                st.success(f"🎉 נמצאו **{len(results)}** מודעות רלוונטיות!")
                st.balloons()
            else:
                st.warning("לא נמצאו מודעות רלוונטיות. נסה קבוצות אחרות או בדוק את ה-API Key.")

    # ══ תוצאות ══
    with tab_results:
        if not st.session_state.get("results"):
            st.info("עדיין אין תוצאות – הרץ סריקה בטאב הראשון.")
        else:
            results = st.session_state["results"]
            st.caption(f"⏱️ {st.session_state.get('scan_time','')} | {len(results)} מודעות")

            f1, f2 = st.columns(2)
            with f1:
                ftype = st.selectbox("סנן לפי סוג", ["הכל","📷 צילום","🎬 עריכה","🎬 עריכה (ריילנס)"])
            with f2:
                fcontact = st.checkbox("רק עם פרטי קשר")

            shown = [r for r in results if ftype == "הכל" or ftype in r["סוג עבודה"]]
            if fcontact:
                shown = [r for r in shown if r["פרטי קשר"] != "—"]

            df = pd.DataFrame(shown)
            table_cols = ["שם המפרסם","סוג עבודה","פרטי קשר","קבוצה","תוכן הפוסט"]
            st.dataframe(
                df[[c for c in table_cols if c in df.columns]],
                use_container_width=True, height=380,
                column_config={"תוכן הפוסט": st.column_config.TextColumn(width="large")},
            )

            st.divider()
            st.subheader("💬 תגובות מוכנות לשליחה")
            for i, row in enumerate(shown):
                with st.expander(f"#{i+1}  |  {row['שם המפרסם']}  |  {row['סוג עבודה']}"):
                    left, right = st.columns([3, 1])
                    with left:
                        st.markdown(f'<div class="reply-card">{row["הצעת תגובה"]}</div>',
                                    unsafe_allow_html=True)
                        if st.button("📋 הצג להעתקה", key=f"btn_{i}"):
                            st.code(row["הצעת תגובה"], language=None)
                    with right:
                        st.markdown(f"**📞** {row['פרטי קשר']}")
                        if row["קישור לפוסט"] != "—":
                            st.markdown(f"[🔗 פתח פוסט]({row['קישור לפוסט']})")

            st.divider()
            e1, e2 = st.columns(2)
            with e1:
                csv = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                st.download_button("⬇️ CSV", csv,
                    file_name=f"jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv", use_container_width=True)
            with e2:
                js = json.dumps(shown, ensure_ascii=False, indent=2).encode("utf-8")
                st.download_button("⬇️ JSON", js,
                    file_name=f"jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json", use_container_width=True)

    # ══ עזרה ══
    with tab_help:
        st.subheader("🛠️ התקנה")
        st.code("pip install streamlit requests pandas\nstreamlit run facebook_job_scanner.py",
                language="bash")

        st.subheader("🔑 איך לקבל Apify API Key")
        st.markdown("""
1. הירשם בחינם בـ [apify.com](https://apify.com)
2. לך לـ **Settings → Integrations**
3. העתק את **Personal API token**
4. הדבק בשדה API Key בסרגל הצד

> התוכנית החינמית נותנת **$5 קרדיט/חודש** – מספיק לעשרות סריקות.
        """)

        st.subheader("⚠️ טיפים")
        st.markdown("""
- **קבוצות פרטיות**: Apify סורק רק קבוצות שהפרופיל שלך חבר בהן
- **עדכון יומי**: מומלץ להריץ פעם בבוקר
- **זמן סריקה**: 2–4 דקות לריצה רגילה
        """)


if __name__ == "__main__":
    main()