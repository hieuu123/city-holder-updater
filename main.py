import base64
import os
import requests
from bs4 import BeautifulSoup

# ================= CONFIG =================
WP_URL = "https://blog.mexc.com/wp-json/wp/v2/posts"
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
URL_SOURCE = "https://miningcombo.com/city-holder/"
POST_ID = 303976  # 🔧 Cập nhật đúng ID bài City Holder Daily Combo
TARGET_H2_EN = "City Holder Daily Quiz Answer – November 21, 2025"
TARGET_H2_RU = "City Holder Daily Quiz Answer For Russia – November 21, 2025"
CHECK_ANSWER = ["Japan", "Monero"]  # hai đáp án đầu tiên để kiểm tra

# ================= SCRAPE =================
def scrape_city_holder():
    print(f"[+] Scraping quiz from {URL_SOURCE}")
    r = requests.get(URL_SOURCE, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # --- List 1: English answers ---
    pre_tag = soup.find("pre", id="tw-target-text")
    if not pre_tag:
        raise RuntimeError("❌ Không tìm thấy <pre id='tw-target-text'> cho List 1")

    raw_text = pre_tag.get_text(separator="\n").strip()
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    list1 = []
    for line in lines:
        # Xóa số thứ tự "01. ", "1. ", "02. "
        cleaned = line.split(".", 1)[-1].strip() if "." in line else line.strip()
        list1.append(cleaned)
    
    print(f"[+] List 1 (EN) có {len(list1)} đáp án")

    # --- List 2: Russian answers ---
    ol_tag = soup.find("ol", class_="wp-block-list")
    if not ol_tag:
        raise RuntimeError("❌ Không tìm thấy <ol class='wp-block-list'> cho List 2")

    list2 = [li.get_text(strip=True) for li in ol_tag.find_all("li") if li.get_text(strip=True)]
    print(f"[+] List 2 (RU) có {len(list2)} đáp án")

    print("   EN sample:", list1[:3])
    print("   RU sample:", list2[:3])
    return list1, list2


# ================= UPDATE WP =================
def update_post_after_h2(target_h2_text, answers, lang_label="EN"):
    if not WP_USERNAME or not WP_APP_PASSWORD:
        raise RuntimeError("⚠️ Thiếu repo secret: WP_USERNAME hoặc WP_APP_PASSWORD")

    token = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASSWORD}".encode()).decode("utf-8")
    headers = {
        "Authorization": f"Basic {token}",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    # 1️⃣ Fetch post content
    url = f"{WP_URL}/{POST_ID}"
    response = requests.get(url, headers=headers, timeout=15)
    print(f"[{lang_label}] 🔎 Fetch status:", response.status_code)
    if response.status_code != 200:
        print(f"[{lang_label}] ❌ Không lấy được post:", response.text[:300])
        return

    post = response.json()
    old_content = post.get("content", {}).get("rendered", "")
    if not old_content:
        print(f"[{lang_label}] ❌ Không thấy content.rendered")
        return

    soup = BeautifulSoup(old_content, "html.parser")

    # 2️⃣ Find target <h2>
    h2_tag = soup.find("h2", string=lambda _: False)  # tránh lỗi None
    for h2 in soup.find_all("h2"):
        if target_h2_text.split("–")[0].strip() in h2.get_text(" ", strip=True):
            h2_tag = h2
            break

    if not h2_tag:
        print(f"[{lang_label}] ❌ Không tìm thấy H2:", target_h2_text)
        return

    # 3️⃣ Remove old <ol>
    next_tag = h2_tag.find_next_sibling()
    removed = 0
    if next_tag and next_tag.name == "ol":
        next_tag.decompose()
        removed += 1
    print(f"[{lang_label}] [+] Removed {removed} <ol> cũ sau H2")

    # 4️⃣ Create new <ol>
    ol_tag = soup.new_tag("ol")
    ol_tag["class"] = "wp-block-list"
    for ans in answers:
        li = soup.new_tag("li")
        li.string = ans
        ol_tag.append(li)

    # 5️⃣ Insert new list
    h2_tag.insert_after(ol_tag)
    new_content = str(soup)

    # 6️⃣ Update post
    payload = {"content": new_content, "status": "publish"}
    update = requests.post(url, headers=headers, json=payload, timeout=15)
    print(f"[{lang_label}] 🚀 Update status:", update.status_code)

    if update.status_code == 200:
        print(f"[{lang_label}] ✅ Post updated thành công!")
    else:
        print(f"[{lang_label}] ❌ Update lỗi:", update.text[:300])


# ================= MAIN =================
if __name__ == "__main__":
    try:
        list1, list2 = scrape_city_holder()

        # check 2 đáp án đầu tiên
        if list1[:2] != CHECK_ANSWER:
            print("✅ List1 khác CHECK_ANSWER -> cập nhật cả EN & RU")
            update_post_after_h2(TARGET_H2_EN, list1, "EN")
            update_post_after_h2(TARGET_H2_RU, list2, "RU")
        else:
            print("⚠️ Đáp án List1 trùng CHECK_ANSWER -> bỏ qua update")

    except Exception as e:
        print("❌ Lỗi khi scrape hoặc update:", e)
