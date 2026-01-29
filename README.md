# Edge Case Handling & Stability Improvements

This document summarizes all major **edge cases identified during scraping automation** and the **solutions implemented** to make the system stable, reliable, and production-ready.

---

## 1️⃣ Incomplete Data Due to Early Stop (Scrolling Logic)

**Edge Case:**  
Scraping stopped too early when a single screen had no new listings, causing missed data.

**Solution:**  
Implemented **Two Consecutive Zeros Logic**:
1. Continue scrolling even if one screen has 0 new listings
2. Stop only after **2 consecutive screens** with no new data
3. Reset counter immediately when new listings are found

**Result:**  
More thorough coverage, minimal risk of missing listings.

---

## 2️⃣ App Slow to Load / Alerts Tab Not Found

**Edge Case:**  
App sometimes loads slowly, causing failure when trying to access the Alerts tab.

**Solution:**  
- Smart wait up to **60 seconds** for Alerts tab to appear  
- Immediate proceed if app loads early  
- Fallback retry mechanism with multiple attempts

**Result:**  
Eliminates flaky startup failures.

---

## 3️⃣ Wrong PDP Opening Due to List Movement

**Edge Case:**  
UI movement or mistouch opens the wrong listing’s PDP.

**Solution:**  
**Wait + Double Verification Strategy**:
1. Stabilization wait before click
2. PDP title verification after opening
3. Second verification after short delay
4. Automatic recovery if mismatch detected

**Result:**  
Wrong listings are detected instantly and skipped safely.

---

## 4️⃣ PDP “Blink” Issue (Listing Changes After Opening)

**Edge Case:**  
Correct PDP opens but switches to another listing after a short delay.

**Solution:**  
- Extra stabilization delay after PDP load  
- Two-step verification to detect post-load changes

**Result:**  
Blinking PDPs are reliably caught and discarded.

---

## 5️⃣ Getting Stuck in PDP When Alert Not Found

**Edge Case:**  
When a target alert is missing, automation may remain stuck inside a PDP.

**Solution:**  
- Detect whether current screen is Alerts or PDP  
- If stuck in PDP ==> navigate back automatically before continuing

**Result:**  
Flow always recovers to a known safe state.

---

## 6️⃣ Accidental PDP Opening During Scroll (Downward)

**Edge Case:**  
Scroll gestures sometimes trigger unintended clicks.

**Solution:**  
- Verify Alerts page after every scroll  
- If PDP opens unexpectedly ==> immediately go back

**Result:**  
Scroll operations remain safe and controlled.

---

## 7️⃣ Accidental PDP Opening During Scroll to Top

**Edge Case:**  
Multiple upward swipes increase chance of accidental PDP opening.

**Solution:**  
- Verification after **each swipe**  
- Immediate recovery if PDP is detected

**Result:**  
Aggressive scrolling without losing page context.

---

## 8️⃣ Scroll to Top Not Reaching Actual Top

**Edge Case:**  
Scroll-to-top stops several listings short of the real top.

**Solution:**  
**Hybrid Scroll Strategy**:
1. Aggressive initial swipes
2. Verification using alert count comparison
3. Additional swipes if needed
4. Final page-state confirmation

**Result:**  
Guaranteed return to true top of the list.

---

## 9️⃣ Duplicate Listings Across Runs

**Edge Case:**  
Same listings appearing across multiple runs or within a single run.

**Solution:**  
- Unique cache key based on listing title + live time  
- Separate tracking for:
  - Historical CSV data
  - Current execution run

**Result:**  
Zero duplicate scraping.

---

## 🔟 No New Listings Scenario

**Edge Case:**  
Endless scrolling when no new data exists.

**Solution:**  
Stop condition triggered after **2 consecutive screens** with zero new listings.

**Result:**  
Efficient exit without unnecessary scrolling.

---
## more to be added, will add as encountered
