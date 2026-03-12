"""
סורק עבודות צילום ועריכה מפייסבוק - Streamlit App
מחפש מודעות בקבוצות פייסבוק ומכין טבלה עם הצעות תגובה
"""

import streamlit as st
import pandas as pd
import time
import random
import json
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ─────────────────────────────────────────────
# הגדרות קבועות
# ─────────────────────────────────────────────
MY_INFO = {
    "name": "אומר",
    "email": "omer7411@gmail.com",
    "phone": "058-743-2288",
    "website": "omerphotos.com",
}

# מילות מפתח לצילום ועריכה
PHOTO_KEYWORDS = [
    "צלם", "צילום", "photographer", "photography",
    "צלמת", "צלמים", "צילומי", "פוטוגרף",
]
EDIT_KEYWORDS = [
    "עורך וידאו", "עריכת וידאו", "עריכה", "מונטאז'",
    "video editor", "video editing", "editor", "post production",
    "עורכת וידאו", "עורך תוכן",
]
REMOTE_KEYWORDS = [
    "מרחוק", "מהבית", "remote", "online", "פרילנס", "freelance",
    "עבודה מהבית", "home office",
]

# קבוצות פייסבוק מומלצות לחיפוש
FACEBOOK_GROUPS = [
    {"name": "צלמים ומצולמים ישראל", "url": "https://www.facebook.com/groups/photographersisrael"},
    {"name": "עורכי וידאו ישראל", "url": "https://www.facebook.com/groups/videoeditors.il"},
    {"name": "פרילנסרים ישראל", "url": "https://www.facebook.com/groups/freelancers.israel"},
    {"name": "עבודות צילום ועריכה", "url": "https://www.facebook.com/groups/photojobs.israel"},
    {"name": "סטודיו והפקות ישראל", "url": "https://www.facebook.com/groups/production.israel"},
]

# ─────────────────────────────────────────────
# פונקציות עזר
# ─────────────────────────────────────────────

def is_relevant_post(text: str) -> tuple[bool, str]:
    """בדוק אם פוסט רלוונטי ואיזה סוג"""
    text_lower = text.lower()
    is_photo = any(kw.lower() in text_lower for kw in PHOTO_KEYWORDS)
    is_edit = any(kw.lower() in text_lower for kw in EDIT_KEYWORDS)
    is_remote = any(kw.lower() in text_lower for kw in REMOTE_KEYWORDS)

    if is_photo:
        return True, "📷 צילום"
    if is_edit:
        if is_remote:
            return True, "🎬 עריכה (ריילנס)"
        return True, "🎬 עריכה"
    return False, ""


def extract_phone(text: str) -> str:
    """חלץ מספר טלפון מהטקסט"""
    patterns = [
        r'0[5-9][0-9]-?[0-9]{7}',
        r'\+972-?[5-9][0-9]-?[0-9]{7}',
        r'05[0-9]{8}',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return ""


def extract_email(text: str) -> str:
    """חלץ כתובת מייל מהטקסט"""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(pattern, text)
    return match.group(0) if match else ""


def generate_reply(post_text: str, job_type: str, poster_name: str) -> str:
    """צור הצעת תגובה מותאמת אישית"""
    is_remote = any(kw.lower() in post_text.lower() for kw in REMOTE_KEYWORDS)

    if "צילום" in job_type:
        service = "צילום מקצועי"
        detail = "צלם עם ניסיון רב בצילומי אירועים, מוצרים ותוכן"
    else:
        service = "עריכת וידאו מקצועית"
        detail = "עורך וידאו עם ניסיון בריילס, רילז, סרטי קידום ותוכן דיגיטלי"

    remote_line = "\n✅ אני עובד גם מרחוק – נוח לכל לקוח!" if is_remote else ""

    reply = f"""היי {poster_name if poster_name else ''}! 👋

ראיתי את הפוסט שלך ואשמח לעזור 🙂
אני {MY_INFO['name']} – {detail}.{remote_line}

📞 {MY_INFO['phone']}
🌐 {MY_INFO['website']}
📧 {MY_INFO['email']}

מוזמן/ת לפנות ונדבר על הפרויקט!"""
    return reply.strip()


# ─────────────────────────────────────────────
# Selenium – סריקה אמיתית
# ─────────────────────────────────────────────

def create_driver(headless: bool = True):
    """צור דרייבר Chrome"""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--lang=he-IL")
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def facebook_login(driver, email: str, password: str) -> bool:
    """התחבר לפייסבוק"""
    try:
        driver.get("https://www.facebook.com/login")
        wait = WebDriverWait(driver, 15)

        email_field = wait.until(EC.presence_of_element_located((By.ID, "email")))
        email_field.clear()
        email_field.send_keys(email)
        time.sleep(random.uniform(0.5, 1.2))

        pass_field = driver.find_element(By.ID, "pass")
        pass_field.clear()
        pass_field.send_keys(password)
        time.sleep(random.uniform(0.5, 1.0))

        pass_field.send_keys(Keys.RETURN)
        time.sleep(random.uniform(4, 6))

        # בדוק אם ההתחברות הצליחה
        if "login" in driver.current_url or "checkpoint" in driver.current_url:
            return False
        return True
    except Exception as e:
        st.error(f"שגיאה בהתחברות: {e}")
        return False


def scan_group(driver, group_url: str, max_posts: int = 30) -> list[dict]:
    """סרוק קבוצה וחזור פוסטים רלוונטיים"""
    results = []
    try:
        driver.get(group_url)
        time.sleep(random.uniform(3, 5))

        wait = WebDriverWait(driver, 10)

        # גלול למטה כדי לטעון עוד פוסטים
        for _ in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2, 3))

        # מצא פוסטים
        post_selectors = [
            '[data-ad-comet-preview="message"]',
            '[data-ad-preview="message"]',
            '.userContent',
            '[role="article"]',
        ]

        posts_elements = []
        for selector in post_selectors:
            posts_elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if posts_elements:
                break

        for post_el in posts_elements[:max_posts]:
            try:
                post_text = post_el.text
                if len(post_text) < 20:
                    continue

                relevant, job_type = is_relevant_post(post_text)
                if not relevant:
                    continue

                # נסה לקבל שם מפרסם
                poster_name = ""
                try:
                    article = post_el.find_element(By.XPATH, "./ancestor::*[@role='article'][1]")
                    name_el = article.find_element(By.CSS_SELECTOR, "h2 a, h3 a, strong a")
                    poster_name = name_el.text
                except Exception:
                    pass

                # נסה לקבל קישור לפוסט
                post_link = ""
                try:
                    article = post_el.find_element(By.XPATH, "./ancestor::*[@role='article'][1]")
                    time_el = article.find_element(By.CSS_SELECTOR, "a[href*='/posts/'], a[href*='?story_fbid=']")
                    post_link = time_el.get_attribute("href")
                except Exception:
                    post_link = group_url

                phone = extract_phone(post_text)
                email = extract_email(post_text)
                contact = phone or email or "לא נמצא"

                reply = generate_reply(post_text, job_type, poster_name)

                results.append({
                    "שם המפרסם": poster_name or "לא ידוע",
                    "סוג עבודה": job_type,
                    "פרטי קשר": contact,
                    "תוכן הפוסט": post_text[:300] + ("..." if len(post_text) > 300 else ""),
                    "הצעת תגובה": reply,
                    "קישור לפוסט": post_link,
                })

            except Exception:
                continue

    except Exception as e:
        st.warning(f"⚠️ שגיאה בסריקת {group_url}: {e}")

    return results


# ─────────────────────────────────────────────
# ממשק Streamlit
# ─────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="סורק עבודות פייסבוק 📷🎬",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # RTL + עיצוב
    st.markdown("""
    <style>
        body, .stApp { direction: rtl; }
        .stTextInput input, .stTextArea textarea { direction: rtl; }
        .stDataFrame { direction: ltr; }
        h1, h2, h3 { color: #1877F2; }
        .reply-box {
            background: #f0f2f5;
            border-right: 4px solid #1877F2;
            padding: 12px;
            border-radius: 8px;
            font-family: monospace;
            white-space: pre-wrap;
            direction: rtl;
        }
        .stat-card {
            background: white;
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 16px;
            text-align: center;
        }
    </style>
    """, unsafe_allow_html=True)

    st.title("🔍 סורק עבודות צילום ועריכה – פייסבוק")
    st.caption("מחפש הזדמנויות עבודה בצילום ועריכת וידאו בישראל")

    # ─── סרגל צד ───
    with st.sidebar:
        st.header("⚙️ הגדרות")

        st.subheader("🔐 כניסה לפייסבוק")
        fb_email = st.text_input("אימייל", placeholder="your@email.com")
        fb_password = st.text_input("סיסמא", type="password")

        st.divider()
        st.subheader("👤 הפרטים שלי (לתגובות)")
        my_name = st.text_input("שם", value=MY_INFO["name"])
        my_phone = st.text_input("טלפון", value=MY_INFO["phone"])
        my_website = st.text_input("אתר", value=MY_INFO["website"])
        my_email_display = st.text_input("מייל", value=MY_INFO["email"])

        st.divider()
        st.subheader("🔧 הגדרות סריקה")
        max_posts = st.slider("פוסטים מקסימום לקבוצה", 10, 100, 30)
        headless_mode = st.checkbox("מצב שקט (ללא חלון)", value=True)

        st.divider()
        st.subheader("📋 קבוצות לסריקה")
        group_names = [g["name"] for g in FACEBOOK_GROUPS]
        selected_groups = st.multiselect(
            "בחר קבוצות",
            options=group_names,
            default=group_names[:3]
        )

        custom_group = st.text_input("➕ קישור קבוצה נוספת (אופציונלי)")

    # ─── ראשי ───
    tab1, tab2, tab3 = st.tabs(["🚀 סריקה חדשה", "📊 תוצאות", "ℹ️ הוראות"])

    with tab1:
        st.subheader("הפעל סריקה")

        col1, col2, col3 = st.columns(3)
        col1.metric("קבוצות שנבחרו", len(selected_groups))
        col2.metric("פוסטים מקסימום", max_posts * len(selected_groups))
        col3.metric("סוגי עבודה", "צילום + עריכה")

        st.info("💡 הסריקה מחפשת אוטומטית מודעות צילום ועריכה ומכינה עבורך תגובות מוכנות לשליחה")

        if st.button("▶️ התחל סריקה", type="primary", use_container_width=True):
            if not fb_email or not fb_password:
                st.error("❌ יש להזין אימייל וסיסמא לפייסבוק")
                st.stop()

            if not selected_groups:
                st.error("❌ יש לבחור לפחות קבוצה אחת")
                st.stop()

            # עדכן MY_INFO עם הפרטים מהצד
            MY_INFO.update({
                "name": my_name,
                "phone": my_phone,
                "website": my_website,
                "email": my_email_display,
            })

            all_results = []
            progress = st.progress(0, text="מתחיל...")
            status = st.empty()

            groups_to_scan = [g for g in FACEBOOK_GROUPS if g["name"] in selected_groups]
            if custom_group and custom_group.startswith("http"):
                groups_to_scan.append({"name": "קבוצה מותאמת", "url": custom_group})

            try:
                status.info("🌐 פותח דפדפן...")
                driver = create_driver(headless=headless_mode)

                status.info("🔐 מתחבר לפייסבוק...")
                logged_in = facebook_login(driver, fb_email, fb_password)

                if not logged_in:
                    st.error("❌ הכניסה לפייסבוק נכשלה. בדוק את הפרטים ונסה שוב.")
                    driver.quit()
                    st.stop()

                st.success("✅ התחברת בהצלחה לפייסבוק!")

                for i, group in enumerate(groups_to_scan):
                    pct = int((i / len(groups_to_scan)) * 100)
                    progress.progress(pct, text=f"סורק: {group['name']}...")
                    status.info(f"🔍 סורק קבוצה: {group['name']}")

                    results = scan_group(driver, group["url"], max_posts)
                    for r in results:
                        r["קבוצה"] = group["name"]
                    all_results.extend(results)

                    time.sleep(random.uniform(2, 4))

                driver.quit()
                progress.progress(100, text="✅ הסריקה הושלמה!")
                status.success(f"🎉 נמצאו {len(all_results)} מודעות רלוונטיות!")

                if all_results:
                    st.session_state["results"] = all_results
                    st.session_state["scan_time"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                    st.balloons()
                else:
                    st.warning("לא נמצאו מודעות רלוונטיות בסריקה זו. נסה קבוצות אחרות.")

            except Exception as e:
                st.error(f"❌ שגיאה בסריקה: {e}")
                st.info("💡 ודא ש-ChromeDriver מותקן: pip install selenium webdriver-manager")

    with tab2:
        st.subheader("📊 תוצאות הסריקה")

        if "results" not in st.session_state or not st.session_state["results"]:
            st.info("🔍 עדיין לא הרצת סריקה. לך ל'סריקה חדשה' והתחל.")
        else:
            results = st.session_state["results"]
            scan_time = st.session_state.get("scan_time", "")

            st.caption(f"⏱️ נסרק בתאריך: {scan_time} | סה\"כ {len(results)} מודעות")

            # סינון
            col1, col2 = st.columns(2)
            with col1:
                filter_type = st.selectbox("סנן לפי סוג", ["הכל", "📷 צילום", "🎬 עריכה", "🎬 עריכה (ריילנס)"])
            with col2:
                filter_contact = st.checkbox("רק עם פרטי קשר")

            filtered = results
            if filter_type != "הכל":
                filtered = [r for r in filtered if filter_type in r["סוג עבודה"]]
            if filter_contact:
                filtered = [r for r in filtered if r["פרטי קשר"] != "לא נמצא"]

            # טבלה ראשית
            df = pd.DataFrame(filtered)
            display_cols = ["שם המפרסם", "סוג עבודה", "פרטי קשר", "קבוצה", "תוכן הפוסט"]
            available_cols = [c for c in display_cols if c in df.columns]

            st.dataframe(
                df[available_cols],
                use_container_width=True,
                height=400,
                column_config={
                    "תוכן הפוסט": st.column_config.TextColumn(width="large"),
                    "קישור לפוסט": st.column_config.LinkColumn(),
                }
            )

            # כרטיסי תגובה
            st.divider()
            st.subheader("💬 הצעות תגובה מוכנות")

            for i, row in enumerate(filtered):
                with st.expander(f"#{i+1} | {row['שם המפרסם']} | {row['סוג עבודה']}"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown("**📝 הצעת תגובה:**")
                        st.markdown(f'<div class="reply-box">{row["הצעת תגובה"]}</div>',
                                    unsafe_allow_html=True)
                        if st.button(f"📋 העתק תגובה #{i+1}", key=f"copy_{i}"):
                            st.code(row["הצעת תגובה"])
                    with col2:
                        st.markdown("**🔗 קישור לפוסט:**")
                        if row.get("קישור לפוסט"):
                            st.markdown(f"[פתח פוסט בפייסבוק]({row['קישור לפוסט']})")
                        st.markdown(f"**📞 קשר:** {row['פרטי קשר']}")

            # ייצוא
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                csv = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                st.download_button(
                    "⬇️ הורד כ-CSV",
                    data=csv,
                    file_name=f"jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with col2:
                json_data = json.dumps(filtered, ensure_ascii=False, indent=2).encode("utf-8")
                st.download_button(
                    "⬇️ הורד כ-JSON",
                    data=json_data,
                    file_name=f"jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json",
                    use_container_width=True,
                )

    with tab3:
        st.subheader("ℹ️ הוראות התקנה והפעלה")
        st.markdown("""
        ### 🛠️ התקנה

        **1. התקן Python ו-pip**

        **2. התקן תלויות:**
        ```bash
        pip install streamlit selenium pandas webdriver-manager
        ```

        **3. התקן ChromeDriver:**
        ```bash
        pip install webdriver-manager
        ```
        אם ChromeDriver לא מותקן אוטומטית, הורד ידנית מ: https://chromedriver.chromium.org

        ### 🚀 הרצה

        ```bash
        streamlit run facebook_job_scanner.py
        ```

        ### 💡 טיפים
        - **ביקורת ידנית**: תמיד עיין בתגובה לפני שליחה
        - **זמן בין סריקות**: מומלץ לחכות שעה בין סריקות
        - **קבוצות**: הוסף קבוצות ספציפיות לתחום שלך
        - **פרטי קשר**: ודא שהפרטים שלך מעודכנים בסרגל הצד

        ### ⚠️ הגבלות
        - פייסבוק עשוי לדרוש אימות נוסף בגישה ממקום חדש
        - מומלץ לא לבצע יותר מ-5 סריקות ביום
        - אם מוצגת בקשת 2FA, היה נוכח בסריקה הראשונה
        """)


if __name__ == "__main__":
    main()
