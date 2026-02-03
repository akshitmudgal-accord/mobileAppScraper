from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from datetime import datetime
import re
import pandas as pd
import json
import os
import shutil

# =====================================================
# APPIUM SETUP
# =====================================================
options = UiAutomator2Options()
options.platform_name = "Android"
#options.device_name = "94d371c9"
options.device_name = "RZ8R81C9GWH"   # galaxy A12S
options.automation_name = "UiAutomator2"
options.app_package = "com.dubizzle.dealerapp"
options.app_activity = "com.dubizzle.dealerapp.MainActivity"
options.no_reset = True
options.full_reset = False
options.auto_grant_permissions = True


# ENSURE APP IS READY

def ensure_app_ready(driver):
    """Ensure app is in foreground and ready to use"""
    print("🔍 Checking app state...")
    
    try:
        # Method 1: Check app state
        app_state = driver.query_app_state("com.dubizzle.dealerapp")
        
        state_descriptions = {
            0: "Not installed",
            1: "Not running",
            2: "Running in background (suspended)",
            3: "Running in background",
            4: "Running in foreground"
        }
        
        state_desc = state_descriptions.get(app_state, "Unknown")
        print(f"  📱 App state: {app_state} ({state_desc})")
        
        if app_state == 0:
            print("❌ App not installed!")
            return False
        elif app_state == 1:
            print("⚠️ App not running, launching...")
            driver.activate_app("com.dubizzle.dealerapp")
            time.sleep(10)
        elif app_state in [2, 3]:
            print("⚠️ App in background, bringing to foreground...")
            driver.activate_app("com.dubizzle.dealerapp")
            time.sleep(5)
        else:
            print("✅ App already in foreground")
        
        # Method 2: Verify app is actually responding
        print("🔍 Verifying app is responsive...")
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Alerts"))
            )
            print("  ✅ App is responsive and ready")
            return True
        except:
            print("⚠️ App not responding to UI queries")
            print("🔄 Attempting restart...")
            
            # Restart app
            try:
                driver.terminate_app("com.dubizzle.dealerapp")
                time.sleep(3)
                print("  📱 App terminated, relaunching...")
                driver.activate_app("com.dubizzle.dealerapp")
                time.sleep(15)
            except Exception as restart_error:
                print(f"  ⚠️ Error during restart: {restart_error}")
                time.sleep(15)
            
            # Final check
            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Alerts"))
                )
                print("✅ App restarted successfully and is responsive")
                return True
            except:
                print("❌ App still not responding after restart")
                return False
                
    except Exception as e:
        print(f"❌ Error checking app state: {e}")
        print("🔄 Attempting to activate app anyway...")
        try:
            driver.activate_app("com.dubizzle.dealerapp")
            time.sleep(10)
            print("✅ App activated")
            return True
        except:
            print("❌ Could not activate app")
            return False

# =====================================================
# DRIVER CONNECTION
# =====================================================
driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
driver.implicitly_wait(7)

# Ensure app is in foreground and ready to handle idle state
if not ensure_app_ready(driver):
    print("❌ Could not ensure app is ready, exiting...")
    driver.quit()
    exit(1)

time.sleep(10)  # Basic initial wait

print("⏳ Waiting for app to fully initialize...")
try:
    # Smart wait - wait up to 60 seconds for Alerts tab to appear
    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Alerts"))
    )
    print("✅ App launched and ready")
except Exception as e:
    print(f"⚠️ App taking longer than expected: {e}")
    print("⏳ Waiting additional 10 seconds...")
    time.sleep(10)
    print("✅ Continuing anyway...")

# ==================================================
# GLOBAL DATA STORE
# ==================================================
pdp_data = {
    "title": None,
    "ref": None,
    "location": None,
    "mileage": None,
    "specs": None,
    "transmission": None,
    "engine_capacity": None,
    "seller_expectation": None,
    "current_bid": None,
    "auction_status": None,
    "auction_end_date": None,
    "live_time": None,  # NEW: capture when it went live
    "cache_key": None,  # NEW: composite key for caching
    "scraped_at": None
}

# List to store all scraped listings
all_listings = []

# Set to track cache keys scraped in current run
current_run_cache_keys = set()

# CSV filename
CSV_FILENAME = "car_listings_cache.csv"

# ==================================================
# LOAD EXISTING CACHE
# ==================================================
def load_existing_cache():
    """Load existing CSV cache if it exists"""
    if os.path.exists(CSV_FILENAME):
        try:
            df = pd.read_csv(CSV_FILENAME, encoding='utf-8-sig')
            print(f"✅ Loaded existing cache: {len(df)} listings")
            # Return set of cache keys for quick lookup
            cache_keys = set(df['cache_key'].dropna().values)
            return df, cache_keys
        except Exception as e:
            print(f"⚠️ Error loading cache: {e}")
            return pd.DataFrame(), set()
    else:
        print("📝 No existing cache found, starting fresh")
        return pd.DataFrame(), set()

# ==================================================
# CREATE BACKUP OF EXISTING CSV
# ==================================================
def backup_existing_csv():
    """Create timestamped backup of existing CSV"""
    if os.path.exists(CSV_FILENAME):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"car_listings_backup_{timestamp}.csv"
        shutil.copy(CSV_FILENAME, backup_filename)
        print(f"💾 Backup created: {backup_filename}")
        return backup_filename
    return None

# ==================================================
# GENERATE CACHE KEY
# ==================================================
def generate_cache_key(title, live_time):
    """Generate composite cache key from title and live time
    Format: 2019_Lincoln_MKZ_Premiere_Tuesday_4:00PM
    """
    if not title or not live_time:
        return None
    
    # Clean title: replace spaces with underscores, remove special chars
    clean_title = re.sub(r'[^\w\s]', '', title.strip())  # Remove special chars
    clean_title = re.sub(r'\s+', '_', clean_title)  # Replace spaces with underscores
    
    # Clean time: "Tuesday at 4:00 PM" -> "Tuesday_4:00PM"
    clean_time = live_time.strip()
    clean_time = clean_time.replace(' at ', '_')  # "Tuesday at 4:00 PM" -> "Tuesday_4:00 PM"
    clean_time = clean_time.replace(' ', '')  # "Tuesday_4:00 PM" -> "Tuesday_4:00PM"
    clean_time = clean_time.replace(':', '')  # "Tuesday_400PM" -> "Tuesday_400PM"
    
    return f"{clean_title}_{clean_time}"

# ==================================================
# CAPTURE HEADER INFO
# ==================================================
def capture_header_info(alert_description=None):
    """Capture title, ref, location, specs, and all header details"""
    try:
        texts = driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")
    except:
        return

    for i in range(len(texts)):
        try:
            txt = texts[i].text.strip()
        except:
            continue

        if not txt:
            continue

        # Title & Ref
        if not pdp_data["title"] and txt.startswith("Ref") and i > 0:
            pdp_data["ref"] = txt
            pdp_data["title"] = texts[i - 1].text
            print(f"   🐧Title: {pdp_data['title']}")
            print(f"   🐧Ref: {pdp_data['ref']}")

        # Location
        if not pdp_data["location"] and txt in ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Fujairah", "Umm Al Quwain"]:
            pdp_data["location"] = txt
            print(f"  📍 Location: {pdp_data['location']}")

        # Mileage
        if not pdp_data["mileage"] and "km" in txt and not txt.startswith("|"):
            pdp_data["mileage"] = txt
            print(f"  🚗 Mileage: {pdp_data['mileage']}")

        # Specs
        if not pdp_data["specs"] and ("GCC Specs" in txt or "American Specs" in txt or "European Specs" in txt or "others" in txt):
            pdp_data["specs"] = txt.replace("|", "").strip()
            print(f"   🐧Specs: {pdp_data['specs']}")

        # Transmission
        if not pdp_data["transmission"] and ("Automatic" in txt or "Manual" in txt) and "|" in txt:
            pdp_data["transmission"] = txt.replace("|", "").strip()
            print(f"  🐧 Transmission: {pdp_data['transmission']}")

        # Engine Capacity
        if not pdp_data["engine_capacity"] and "cc" in txt and "|" in txt:
            pdp_data["engine_capacity"] = txt.replace("|", "").strip()
            print(f"  🐧 Engine Capacity: {pdp_data['engine_capacity']}")

        # Seller Expectation
        if txt == "Seller Expectation" and i > 0:
            pdp_data["seller_expectation"] = texts[i - 1].text
            print(f"  🐧Seller Expectation: {pdp_data['seller_expectation']}")

        # Current Bid
        if txt == "Current Bid" and i > 0:
            pdp_data["current_bid"] = texts[i - 1].text
            print(f"  🐧Current Bid: {pdp_data['current_bid']}")

        # Auction Status & End Date
        if txt == "Auction ended" and i + 1 < len(texts):
            pdp_data["auction_status"] = "Ended"
            pdp_data["auction_end_date"] = texts[i + 1].text
            print(f"  🐧Auction Status: {pdp_data['auction_status']}")
            print(f"  🐧Auction End Date: {pdp_data['auction_end_date']}")
    
    # Extract live time from alert description
    if alert_description:
        # Extract time pattern like "Tuesday at 3:41 PM"
        time_match = re.search(r'((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+at\s+\d{1,2}:\d{2}\s+(?:AM|PM))', alert_description)
        if time_match:
            pdp_data["live_time"] = time_match.group(1)
            print(f"  ⏰ Live Time: {pdp_data['live_time']}")
    
    # Generate cache key
    if pdp_data["title"] and pdp_data["live_time"]:
        pdp_data["cache_key"] = generate_cache_key(pdp_data["title"], pdp_data["live_time"])
        print(f"  🔑 Cache Key: {pdp_data['cache_key']}")

# ==================================================
# OPEN ALERTS TAB
# ==================================================
def open_alerts_tab():
    """Open Alerts tab with retry logic"""
    print("🔔 Opening Alerts tab")
    
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"  📍 Attempt {attempt}/{max_attempts}...")
            driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Alerts").click()
            time.sleep(3)
            print("✅ Alerts tab opened")
            return True
        except Exception as e:
            if attempt < max_attempts:
                wait_time = 10
                print(f"  ⚠️ Failed: {e}")
                print(f"  ⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                print(f"❌ Failed to open Alerts after {max_attempts} attempts")
                print(f"      Last error: {e}")
                return False
    
    return False

# ==================================================
# SCROLL DOWN IN ALERTS
# ==================================================
def scroll_down_alerts():
    """Scroll down in alerts list to load more items with verification and recovery"""
    print("\n⬇️ Scrolling down to load more alerts...")
    try:
        # Small delay to ensure list is stable
        time.sleep(0.5)
        
        size = driver.get_window_size()
        
        # Swipe up to scroll down
        driver.swipe(
            size["width"] // 2,
            int(size["height"] * 0.7),
            size["width"] // 2,
            int(size["height"] * 0.3),
            1000
        )
        time.sleep(3)
        
        # VERIFY we're still on alerts page (didn't accidentally open PDP)
        try:
            # Check if Alerts tab is still accessible (means we're on alerts page)
            alerts_tab = driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Alerts")
            print("✅ Scrolled down")
            return True
        except:
            # We accidentally opened a PDP during scroll
            print("⚠️ Accidentally opened PDP during scroll!")
            print("⬅️ Going back to alerts...")
            try:
                driver.back()
                time.sleep(3)
                print("✅ Returned to alerts after accidental PDP open")
                return True
            except Exception as back_error:
                print(f"❌ Could not go back: {back_error}")
                return False
                
    except Exception as e:
        print(f"⚠️ Error during scroll: {e}")
        
        # Try to recover if we accidentally opened a PDP
        try:
            print("🔄 Attempting to recover...")
            driver.back()
            time.sleep(3)
            print("✅ Recovered - back at alerts")
            return True
        except:
            print("❌ Could not recover")
            return False

# ==================================================
# SCROLL TO TOP OF ALERTS
# ==================================================
def scroll_to_top_alerts():
    """Scroll to the very top of alerts list with verification (Hybrid Approach)"""
    print("\n⬆️ Scrolling to top of alerts...")
    try:
        size = driver.get_window_size()
        
        # Step 1: Aggressive scrolling to top (7 swipes with longer range)
        print("  🔄 Step 1: Aggressive scroll to top...")
        for i in range(7):
            # Small delay before each swipe to prevent accidental clicks
            time.sleep(0.3)
            
            driver.swipe(
                size["width"] // 2,
                int(size["height"] * 0.2),  # Start higher (20% from top)
                size["width"] // 2,
                int(size["height"] * 0.8),  # End lower (80% from top)
                1000  # Longer duration for smoother scroll
            )
            time.sleep(0.3)  # Brief pause between swipes
            
            # Check if we accidentally opened a PDP
            try:
                driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Alerts")
            except:
                print(f"  ⚠️ Accidentally opened PDP during scroll #{i+1}, going back...")
                try:
                    driver.back()
                    time.sleep(2)
                    print(f"  ✅ Recovered from accidental PDP open")
                except:
                    print(f"  ❌ Could not recover, stopping scroll to top")
                    return False
        
        print("  😎 Initial scroll complete")
        time.sleep(1)
        
        # Step 2: Verify we're at top by checking if content changes
        print("  🔍 Step 2: Verifying we reached top...")
        try:
            # First verify we're still on alerts page
            try:
                driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Alerts")
            except:
                print("  ⚠️ Not on alerts page, going back...")
                driver.back()
                time.sleep(2)
            
            live_alerts_before = get_all_live_alerts()
            before_count = len(live_alerts_before)
            print(f"    Alerts visible before verification swipe: {before_count}")
            
            # Small delay before verification swipe
            time.sleep(0.5)
            
            # Try one more swipe
            driver.swipe(
                size["width"] // 2,
                int(size["height"] * 0.2),
                size["width"] // 2,
                int(size["height"] * 0.8),
                1000
            )
            time.sleep(1)
            
            # Check if we're still on alerts after verification swipe
            try:
                driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Alerts")
            except:
                print("  ⚠️ Accidentally opened PDP during verification, going back...")
                driver.back()
                time.sleep(2)
            
            live_alerts_after = get_all_live_alerts()
            after_count = len(live_alerts_after)
            print(f"    Alerts visible after verification swipe: {after_count}")
            
            # If alert count didn't change (or changed minimally), we're at top
            if abs(before_count - after_count) <= 1:
                print("  ✅ Confirmed: We are at the top!")
            else:
                print("  ⚠️ Not quite at top yet, doing additional swipes...")
                # Step 3: Do a few more swipes to be absolutely sure
                for i in range(5):
                    time.sleep(0.4)
                    
                    driver.swipe(
                        size["width"] // 2,
                        int(size["height"] * 0.2),
                        size["width"] // 2,
                        int(size["height"] * 0.8),
                        1000
                    )
                    time.sleep(0.4)
                    
                    # Check for accidental PDP open
                    try:
                        driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Alerts")
                    except:
                        print(f"  ⚠️ Accidentally opened PDP during additional scroll #{i+1}, going back...")
                        try:
                            driver.back()
                            time.sleep(2)
                        except:
                            print(f"  ❌ Could not recover")
                            return False
                
                print("  ✅ Additional swipes complete")
        
        except Exception as e:
            print(f"  ⚠️ Could not verify top position: {e}")
            print("  ℹ️ Proceeding anyway (initial scroll should be sufficient)")
        
        # Final check - make sure we're on alerts page
        try:
            driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Alerts")
            print("✅ Scrolled to top and on alerts page")
        except:
            print("⚠️ Not on alerts page after scroll, going back...")
            try:
                driver.back()
                time.sleep(2)
                print("✅ Recovered - back at alerts")
            except:
                print("❌ Could not return to alerts")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error during scroll to top: {e}")
        # Try to recover
        try:
            print("🔄 Attempting to recover...")
            driver.back()
            time.sleep(2)
            print("✅ Recovered")
            return True
        except:
            print("❌ Could not recover")
            return False

# ==================================================
# REFRESH ALERTS TAB
# ==================================================
def refresh_alerts_tab():
    """Refresh alerts tab by swiping down"""
    print("\n🔄 Refreshing Alerts tab...")
    try:
        size = driver.get_window_size()
        # Swipe down from top to refresh
        driver.swipe(
            size["width"] // 2,
            int(size["height"] * 0.3),
            size["width"] // 2,
            int(size["height"] * 0.7),
            1000
        )
        time.sleep(6)  # Wait for refresh to complete
        print("✅ Alerts tab refreshed")
        return True
    except Exception as e:
        print(f"⚠️ Could not refresh: {e}")
        return False

# ==================================================
# GET ALL LIVE ALERTS
# ==================================================
def get_all_live_alerts():
    """Get all live alert cards with their descriptions"""
    try:
        cards = driver.find_elements(
            AppiumBy.ANDROID_UIAUTOMATOR,
            'new UiSelector().className("android.view.ViewGroup").clickable(true)'
        )
    except Exception as e:
        print(f"❌ Could not find alert cards: {e}")
        return []
    
    live_alerts = []
    for card in cards:
        try:
            desc = card.get_attribute("content-desc")
            if desc and "is now Live" in desc:
                live_alerts.append((card, desc))
        except:
            continue
    
    return live_alerts

# ==================================================
# EXTRACT CACHE KEYS FROM ALERTS
# ==================================================
def extract_cache_keys_from_alerts(live_alerts):
    """Extract cache keys from alert descriptions without opening them"""
    cache_keys = []
    for _, alert_desc in live_alerts:
        # Extract title (everything before "is now Live")
        title_match = re.search(r'^(.+?)\s+is now Live', alert_desc)
        # Extract time
        time_match = re.search(r'((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+at\s+\d{1,2}:\d{2}\s+(?:AM|PM))', alert_desc)
        
        if title_match and time_match:
            title = title_match.group(1).strip()
            live_time = time_match.group(1)
            cache_key = generate_cache_key(title, live_time)
            cache_keys.append((cache_key, alert_desc))
    
    return cache_keys

# ==================================================
# RESET PDP DATA
# ==================================================
def reset_pdp_data():
    """Reset pdp_data for next listing"""
    global pdp_data
    
    pdp_data = {
        "title": None,
        "ref": None,
        "location": None,
        "mileage": None,
        "specs": None,
        "transmission": None,
        "engine_capacity": None,
        "seller_expectation": None,
        "current_bid": None,
        "auction_status": None,
        "auction_end_date": None,
        "live_time": None,
        "cache_key": None,
        "scraped_at": None
    }

# ==================================================
# SAVE CURRENT LISTING TO LIST
# ==================================================
def save_current_listing():
    """Save current pdp_data to the all_listings list"""
    listing_copy = {
        "title": pdp_data["title"],
        "ref": pdp_data["ref"],
        "location": pdp_data["location"],
        "mileage": pdp_data["mileage"],
        "specs": pdp_data["specs"],
        "transmission": pdp_data["transmission"],
        "engine_capacity": pdp_data["engine_capacity"],
        "seller_expectation": pdp_data["seller_expectation"],
        "current_bid": pdp_data["current_bid"],
        "auction_status": pdp_data["auction_status"],
        "auction_end_date": pdp_data["auction_end_date"],
        "live_time": pdp_data["live_time"],
        "cache_key": pdp_data["cache_key"],
        "scraped_at": pdp_data["scraped_at"]
    }
    
    all_listings.append(listing_copy)
    
    # Add to current run cache keys
    if pdp_data["cache_key"]:
        current_run_cache_keys.add(pdp_data["cache_key"])
    
    print(f"✅ Listing saved (Total: {len(all_listings)})")

# ==================================================
# SCRAPE SINGLE PDP HEADER
# ==================================================
def scrape_pdp_header(alert_description):
    """Scrape only header info from PDP"""
    print("\n" + "="*60)
    print("📄 SCRAPING PDP HEADER")
    print("="*60)
    
    pdp_data["scraped_at"] = datetime.utcnow()
    
    # Capture header info
    print("\n📊 Capturing header info...")
    capture_header_info(alert_description)
    
    # Print results
    print("\n" + "="*60)
    print("✅ HEADER DATA CAPTURED")
    print("="*60)
    print(f"Title: {pdp_data['title']}")
    print(f"Ref: {pdp_data['ref']}")
    print(f"Location: {pdp_data['location']}")
    print(f"Mileage: {pdp_data['mileage']}")
    print(f"Specs: {pdp_data['specs']}")
    print(f"Transmission: {pdp_data['transmission']}")
    print(f"Engine Capacity: {pdp_data['engine_capacity']}")
    print(f"Seller Expectation: {pdp_data['seller_expectation']}")
    print(f"Current Bid: {pdp_data['current_bid']}")
    print(f"Auction Status: {pdp_data['auction_status']}")
    print(f"Auction End Date: {pdp_data['auction_end_date']}")
    print(f"Live Time: {pdp_data['live_time']}")
    print(f"Cache Key: {pdp_data['cache_key']}")
    print(f"Scraped at: {pdp_data['scraped_at']}")
    print("="*60)
    
    # Save to list
    save_current_listing()

# ==================================================
# GO BACK TO ALERTS
# ==================================================
def go_back_to_alerts():
    """Navigate back to Alerts tab"""
    print("\n⬅️ Going back to Alerts tab...")
    try:
        driver.back()
        time.sleep(3)
        print("✅ Back to Alerts tab")
        return True
    except Exception as e:
        print(f"⚠️ Could not go back: {e}")
        return False

# ==================================================
# SAVE TO CSV
# ==================================================
def save_to_csv(existing_df=None):
    """Save all listings to CSV file, merging with existing data if provided"""
    if not all_listings:
        print("⚠️ No new data to save")
        return
    
    # Create DataFrame from new listings
    new_df = pd.DataFrame(all_listings)
    
    # Merge with existing data if provided
    if existing_df is not None and not existing_df.empty:
        # Combine old and new data
        df = pd.concat([existing_df, new_df], ignore_index=True)
        # Remove duplicates based on cache_key (keep first occurrence)
        df = df.drop_duplicates(subset=['cache_key'], keep='first')
        print(f"📊 Merged with existing data: {len(existing_df)} old + {len(new_df)} new = {len(df)} total")
    else:
        df = new_df
    
    # Save to CSV
    df.to_csv(CSV_FILENAME, index=False, encoding='utf-8-sig')
    
    print(f"\n{'='*60}")
    print(f"💾 DATA SAVED TO CSV")
    print(f"{'='*60}")
    print(f"📁 Filename: {CSV_FILENAME}")
    print(f"📊 Total listings: {len(df)}")
    print(f"📋 New listings added: {len(new_df)}")
    print(f"\n📝 Columns:")
    for col in df.columns:
        print(f"  *️⃣ {col}")
    print(f"{'='*60}")
    
    return CSV_FILENAME

# ==================================================
# SCRAPE NEW ALERTS FROM CURRENT SCREEN
# ==================================================
def scrape_new_alerts_on_screen(existing_cache_keys):
    """
    Scrape new alerts visible on current screen
    Returns: number of new alerts scraped
    """
    # Get current screen alerts
    live_alerts = get_all_live_alerts()
    print(f"📊 Found {len(live_alerts)} live alerts on screen")
    
    # Extract cache keys
    alert_cache_keys = extract_cache_keys_from_alerts(live_alerts)
    
    # Combined cache: CSV + current run
    combined_cache = existing_cache_keys.union(current_run_cache_keys)
    
    # Find new alerts
    new_alerts = []
    for cache_key, alert_desc in alert_cache_keys:
        if cache_key not in combined_cache:
            new_alerts.append((cache_key, alert_desc))
            print(f"  🆕 New: {alert_desc}")
        else:
            print(f"  📦 Cached: {alert_desc}")
    
    print(f"\n📈 Summary: {len(new_alerts)} new, {len(alert_cache_keys) - len(new_alerts)} cached")
    
    # Scrape new alerts if any
    alerts_scraped = 0
    if new_alerts:
        for cache_key, alert_desc in new_alerts:
            print(f"\n{'='*60}")
            print(f"📩 PROCESSING: {alert_desc}")
            print(f"{'='*60}")
            
            # Extract expected title from alert description
            title_match = re.search(r'^(.+?)\s+is now Live', alert_desc)
            expected_title = title_match.group(1).strip() if title_match else None
            
            # Find and click the matching alert
            found = False
            live_alerts = get_all_live_alerts()  # Refresh list
            
            for card, desc in live_alerts:
                if desc == alert_desc:
                    try:
                        # Wait for list to stabilize before clicking
                        print("  ⏳ Waiting for list to stabilize...")
                        time.sleep(1)
                        
                        # Click the alert
                        card.click()
                        time.sleep(5)
                        found = True
                        
                        # STEP 1: Extra stabilization delay (let PDP fully load and settle)
                        print("  ⏳ Waiting for PDP to fully stabilize...")
                        time.sleep(2)
                        
                        # STEP 2: First title verification
                        print("  🔍 First verification - checking opened PDP...")
                        try:
                            texts = driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")
                            actual_title = None
                            
                            # Find the actual title in PDP
                            for i in range(len(texts)):
                                try:
                                    txt = texts[i].text.strip()
                                    if txt.startswith("Ref") and i > 0:
                                        actual_title = texts[i - 1].text.strip()
                                        break
                                except:
                                    continue
                            
                            #NEW: If title is None, PDP didn't load - retry click
                            if actual_title is None:
                                print(f"  ⚠️ PDP did not load (title is None)")
                                print(f"  🔄 Retrying click with longer wait...")
                                
                                # Go back first (in case we're stuck somewhere)
                                try:
                                    driver.back()
                                    time.sleep(2)
                                except:
                                    pass
                                
                                # Refresh the alert list and find the card again
                                live_alerts_retry = get_all_live_alerts()
                                card_found = False
                                
                                for card_retry, desc_retry in live_alerts_retry:
                                    if desc_retry == alert_desc:
                                        try:
                                            print("  👆 Attempting second click...")
                                            time.sleep(1)
                                            card_retry.click()
                                            time.sleep(7)  # Longer wait on retry
                                            time.sleep(3)  # Extra stabilization
                                            
                                            # Try to get title again
                                            texts_retry = driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")
                                            actual_title = None
                                            
                                            for i in range(len(texts_retry)):
                                                try:
                                                    txt = texts_retry[i].text.strip()
                                                    if txt.startswith("Ref") and i > 0:
                                                        actual_title = texts_retry[i - 1].text.strip()
                                                        break
                                                except:
                                                    continue
                                            
                                            if actual_title is None:
                                                print(f"  ❌ PDP still did not load after retry")
                                                print(f"  ⬅️ Going back and skipping this listing...")
                                                try:
                                                    driver.back()
                                                    time.sleep(2)
                                                except:
                                                    pass
                                                card_found = True
                                                break
                                            else:
                                                print(f"  ✅ PDP loaded successfully on retry: {actual_title}")
                                                card_found = True
                                                break
                                        except Exception as retry_error:
                                            print(f"  ❌ Error during retry: {retry_error}")
                                            break
                                
                                if not card_found or actual_title is None:
                                    break  # Skip to next alert in outer loop
                            
                            # Compare titles on first check (if we got a title)
                            if actual_title and expected_title:
                                if actual_title != expected_title:
                                    print(f"  ❌ WRONG PDP on first check!")
                                    print(f"     Expected: {expected_title}")
                                    print(f"     Got: {actual_title}")
                                    print("  ⬅️ Going back and skipping this listing...")
                                    go_back_to_alerts()
                                    time.sleep(2)
                                    break  # Skip to next alert in outer loop
                                else:
                                    print(f"  ✅ First check passed: {actual_title}")
                            elif actual_title is None:
                                # Already handled by retry logic above
                                print(f"  ℹ️ Skipping due to PDP load failure")
                                break
                            else:
                                print(f"  ⚠️ Could not verify on first check (Expected: {expected_title}, Got: {actual_title})")
                                print("  ℹ️ Proceeding to second verification...")
                        
                        except Exception as verify_error:
                            print(f"  ⚠️ Error during first verification: {verify_error}")
                            print("  ℹ️ Proceeding to second verification...")
                        
                        # Check if we should continue (title must not be None at this point)
                        if actual_title is None:
                            break  # Skip to next alert
                        
                        # STEP 3: Wait and re-verify (catch the "blink" issue)
                        print("  🔍 Second verification - checking if PDP changed...")
                        time.sleep(1)
                        
                        try:
                            texts = driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")
                            actual_title_second = None
                            
                            # Find the actual title in PDP again
                            for i in range(len(texts)):
                                try:
                                    txt = texts[i].text.strip()
                                    if txt.startswith("Ref") and i > 0:
                                        actual_title_second = texts[i - 1].text.strip()
                                        break
                                except:
                                    continue
                            
                            # Compare titles on second check
                            if actual_title_second and expected_title:
                                if actual_title_second != expected_title:
                                    print(f"  ❌ PDP CHANGED after opening (blinked)!")
                                    print(f"     Expected: {expected_title}")
                                    print(f"     Got: {actual_title_second}")
                                    print("  ⬅️ Going back and skipping this listing...")
                                    go_back_to_alerts()
                                    time.sleep(2)
                                    break  # Skip to next alert in outer loop
                                else:
                                    print(f"  ✅ Second check passed: {actual_title_second}")
                                    print("  ✅ PDP is stable and correct!")
                            else:
                                print(f"  ⚠️ Could not verify on second check (Expected: {expected_title}, Got: {actual_title_second})")
                                print("  ℹ️ Proceeding with scraping anyway...")
                        
                        except Exception as verify_error:
                            print(f"  ⚠️ Error during second verification: {verify_error}")
                            print("  ℹ️ Proceeding with scraping anyway...")
                        
                        break  # Exit the card search loop
                        
                    except Exception as e:
                        print(f"❌ Could not click alert: {e}")
                        continue
            
            if not found:
                # STEP 4: Check if we're stuck in a PDP instead of on alerts page
                print(f"⚠️ Alert not found in list")
                try:
                    # Try to find Alerts tab - if found, we're on alerts page
                    driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Alerts")
                    print("  ℹ️ Confirmed on alerts page, skipping this listing")
                except:
                    # Alerts tab not found - we're stuck in a PDP
                    print("  ⚠️ We're stuck in a PDP! Going back to alerts...")
                    try:
                        driver.back()
                        time.sleep(2)
                        print("  ✅ Returned to alerts page")
                    except Exception as back_error:
                        print(f"  ❌ Could not go back: {back_error}")
                finally:
                    print("  ⚠️ Skipping this listing")
                    continue
            
            # Check if we skipped due to wrong PDP (verify we're still on correct PDP)
            try:
                texts = driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")
                current_title = None
                for i in range(len(texts)):
                    try:
                        txt = texts[i].text.strip()
                        if txt.startswith("Ref") and i > 0:
                            current_title = texts[i - 1].text.strip()
                            break
                    except:
                        continue
                
                # If we're back at alerts (no title found), skip scraping
                if not current_title:
                    print("  ℹ️ Back at alerts list, skipping scraping for this item")
                    continue
                
                # If title doesn't match expected, we already went back
                if expected_title and current_title and current_title != expected_title:
                    print("  ℹ️ Wrong PDP detected, already went back, skipping")
                    continue
                    
            except:
                pass  # If check fails, proceed with scraping
            
            # Reset data for new listing
            reset_pdp_data()
            
            # Scrape the PDP header
            try:
                scrape_pdp_header(alert_desc)
                alerts_scraped += 1
            except Exception as e:
                print(f"❌ Error scraping PDP: {e}")
            
            # Go back to alerts tab
            if not go_back_to_alerts():
                print("❌ Could not return to Alerts tab, stopping")
                break
            time.sleep(2)
    
    return alerts_scraped

# ==================================================
# MAIN SCRAPING WITH SCROLL PAGINATION
# ==================================================
def run_scroll_based_scraping():
    """
    Main scraping logic with scroll pagination:
    1. Scrape initial screen
    2. Scroll down repeatedly, scraping new listings each time
    3. Stop when no new listings found on 2 CONSECUTIVE screens
    4. Scroll to top and refresh for brand new listings
    """
    # Load existing cache
    existing_df, existing_cache_keys = load_existing_cache()
    
    # Create backup if we have existing data
    if not existing_df.empty:
        backup_existing_csv()
    
    if not open_alerts_tab():
        return False
    
    print("\n" + "="*60)
    print("🚀 STARTING SCROLL-BASED SCRAPING")
    print("="*60)
    
    total_scraped = 0
    scroll_count = 0
    consecutive_zero_count = 0  # Track consecutive screens with 0 new listings
    max_scrolls = 50  # Safety limit to prevent infinite scrolling
    
    # Phase 1: Scroll and scrape
    print("\n" + "#"*60)
    print("📜 PHASE 1: SCROLL & SCRAPE")
    print("#"*60)
    
    while scroll_count < max_scrolls and consecutive_zero_count < 2:  # Stop after 2 consecutive zeros
        scroll_count += 1
        print(f"\n{'='*60}")
        print(f"📄 SCREEN #{scroll_count}")
        print(f"{'='*60}")
        
        # Scrape new alerts on current screen
        scraped = scrape_new_alerts_on_screen(existing_cache_keys)
        total_scraped += scraped
        
        if scraped == 0:
            #  Increment consecutive zero counter
            consecutive_zero_count += 1
            print(f"\n⚠️ No new listings found on screen #{scroll_count}")
            print(f"⚠️ Strike {consecutive_zero_count}/2")
            
            if consecutive_zero_count >= 2:
                print(f"\n✅ No new listings for 2 consecutive screens")
                print("🛑 Stopping scroll pagination")
                break
            else:
                print(f"\n🔄 Scrolling once more to double-check...")
        else:
            #  Reset counter when we find new listings
            consecutive_zero_count = 0
            print(f"\n✅ Scraped {scraped} new listings from screen #{scroll_count}")
            print(f"✅ Resetting consecutive zero counter")
        
        # Scroll down for next batch (if not at the stopping condition)
        if consecutive_zero_count < 2 and scroll_count < max_scrolls:
            if not scroll_down_alerts():
                print("⚠️ Could not scroll down, stopping")
                break
    
    # Save data from scroll phase
    if total_scraped > 0:
        print(f"\n{'='*60}")
        print(f"💾 SAVING SCROLL PHASE DATA")
        print(f"{'='*60}")
        save_to_csv(existing_df)
        # Reload cache with newly scraped data
        existing_df, existing_cache_keys = load_existing_cache()
    else:
        print(f"\nℹ️ No new listings scraped during scroll phase")
    
    # Phase 2: Scroll to top and refresh
    print("\n" + "#"*60)
    print("🔄 PHASE 2: REFRESH FOR NEW LISTINGS")
    print("#"*60)
    
    # Scroll to top
    scroll_to_top_alerts()
    time.sleep(2)
    
    # Refresh
    refresh_alerts_tab()
    
    # Check for brand new listings after refresh
    print(f"\n{'='*60}")
    print("🔍 CHECKING FOR NEW LISTINGS AFTER REFRESH")
    print(f"{'='*60}")
    
    refresh_scraped = scrape_new_alerts_on_screen(existing_cache_keys)
    
    if refresh_scraped > 0:
        print(f"\n✅ Scraped {refresh_scraped} new listings after refresh")
        total_scraped += refresh_scraped
        save_to_csv(existing_df)
    else:
        print("\n✅ No new listings found after refresh")
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"✅ SCRAPING COMPLETE")
    print(f"{'='*60}")
    print(f"📊 Total screens processed: {scroll_count}")
    print(f"📊 Total listings scraped: {total_scraped}")
    print(f"📊 Consecutive zero count at end: {consecutive_zero_count}")
    print(f"{'='*60}")
    
    return True

# ==================================================
# RUN THE SCRAPER
# ==================================================
try:
    run_scroll_based_scraping()
except Exception as e:
    print(f"\n❌ Error during scraping: {e}")
    import traceback
    traceback.print_exc()
finally:
    print("\n🔒 Closing app completely...")
    try:
        driver.terminate_app("com.dubizzle.dealerapp")
        print("✅ App closed and removed from recents")
        print("🔐 Login session preserved (no_reset=True)")
    except Exception as e:
        print(f"⚠️ Could not terminate app: {e}")
    
    driver.quit()
    print("\n✅ Session closed")