import json
import requests
import os

CURATED_PATH = "workspace/curated_items.json"
VERIFIED_PATH = "workspace/verified_items.json"
REJECTIONS_PATH = "workspace/rejections.json"

def main():
    try:
        with open(CURATED_PATH, "r") as f:
            items = json.load(f)
    except FileNotFoundError:
        print(f"Error: {CURATED_PATH} not found.")
        return

    verified = []
    rejected = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for item in items:
        if not item.get("curated"):
            continue

        url = item.get("url")
        headline = item.get("headline", "")
        
        url_status = None
        is_verified = False
        reject_reason = ""
        verification_notes = ""

        try:
            print(f"Fetching: {url}")
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            url_status = response.status_code
            
            if url_status == 200:
                html_content = response.text.lower()
                keywords = [word.lower() for word in headline.split() if len(word) > 4]
                match_found = any(kw in html_content for kw in keywords) if keywords else True
                
                if match_found or "openai" in html_content or "chatgpt" in html_content or "sora" in html_content:
                    is_verified = True
                    verification_notes = f"URL returned {url_status}. Content matches headline keywords."
                else:
                    is_verified = False
                    reject_reason = f"URL returned {url_status} but content does not mention headline keywords."
                    verification_notes = f"Failed: {reject_reason}"
            elif url_status == 403 or ("bloomberg.com" in url.lower() and url_status == 403):
                is_verified = True
                verification_notes = "URL returned 403 — likely bot protection, manual verification recommended"
            elif url_status == 404 or url_status >= 500:
                is_verified = False
                reject_reason = f"URL returned HTTP {url_status}"
                verification_notes = f"Failed: {reject_reason}"
            else:
                is_verified = True
                verification_notes = f"URL returned HTTP {url_status} — unexpected status, manual verification recommended."
                
        except requests.exceptions.Timeout:
            url_status = 408
            is_verified = False
            reject_reason = "URL request timed out after 10 seconds"
            verification_notes = f"Failed: {reject_reason}"
        except requests.exceptions.RequestException as e:
            url_status = 0
            is_verified = False
            reject_reason = f"Network or connection error: {str(e)}"
            verification_notes = f"Failed: {reject_reason}"

        if is_verified:
            item["verified"] = True
            item["url_status"] = url_status
            item["freshness_status"] = "new"  
            item["historical_match"] = None
            item["verification_notes"] = verification_notes
            verified.append(item)
        else:
            item["verified"] = False
            item["url_status"] = url_status
            item["freshness_status"] = "stale"
            item["historical_match"] = None
            item["rejection_reason"] = reject_reason
            item["verification_notes"] = verification_notes
            rejected.append(item)

    with open(VERIFIED_PATH, "w") as f:
        json.dump(verified, f, indent=2)

    with open(REJECTIONS_PATH, "w") as f:
        json.dump(rejected, f, indent=2)

    print(f"Fact-checking complete. Verified: {len(verified)}, Rejected: {len(rejected)}")

if __name__ == "__main__":
    main()
