"""
One-time seed script for the CREET Support knowledge base.
Run with: python3 seed_knowledge.py
Safe to re-run — skips articles that already exist by title.
"""
from database import SessionLocal
import models

ARTICLES = [
    ("Getting Started", "What is CREET?",
     "CREET is a marketplace where Buyers can hire Freelancers or purchase Products from Vendors, all in one place. "
     "Each account has exactly one role: Buyer, Freelancer, or Vendor."),
    ("Getting Started", "Choosing a role",
     "You pick your role (Freelancer, Buyer, or Vendor) when you sign up. Each role sees a different home feed: "
     "Freelancers see open Requests, Vendors see open Requests, and Buyers see Freelancers and Products."),

    ("Account & Authentication", "How to sign up",
     "Sign up with email/password (3-step form: name & details, email & password, terms) or with Google sign-in. "
     "Email signups require a 6-digit verification code sent to your inbox before you can log in."),
    ("Account & Authentication", "Resetting your password",
     "On the login page, tap 'Forgot password?', enter your email, and we'll send a reset code. "
     "Enter that code on the next screen along with your new password (minimum 8 characters)."),
    ("Account & Authentication", "Changing your password while logged in",
     "Go to Settings > Account & password. Enter your current password and your new password, then tap Update password."),
    ("Account & Authentication", "Deleting your account",
     "Go to Settings > Account & password > Delete my account. You'll need to confirm with your password. "
     "This permanently deletes your account and cannot be undone."),
    ("Account & Authentication", "Account suspension",
     "Accounts can be suspended for 24 hours (temporary) or 30 days (serious) after receiving multiple reports or "
     "one severe report. Suspended accounts self-release automatically once the suspension period ends."),

    ("Profiles", "Editing your profile",
     "Go to Profile > Edit profile. You can change your name, username, Bio (a short public line shown on your "
     "profile), About (private notes CREET uses to personalize your feed, not shown publicly), location, and skill categories."),
    ("Profiles", "Profile photo and cover photo",
     "On your Profile page, tap the camera icon on your avatar or cover banner to upload a new photo. "
     "You can crop and reposition the image before saving."),
    ("Profiles", "Verified badge",
     "The verified badge is included automatically with a Premium subscription — there's no separate identity "
     "verification step. See Settings > Get Premium."),

    ("Connections", "What are Connections?",
     "Connections are like a professional network within CREET — connect with other users to see their listings "
     "in a dedicated feed and build trust."),
    ("Connections", "Sending and accepting connection requests",
     "Visit someone's profile and tap Connect. They'll get a notification and can Accept or Decline from their "
     "Connections page."),

    ("Following", "Following vs Connecting",
     "CREET currently uses Connections (mutual, like LinkedIn) rather than one-way following. To stay updated on "
     "someone's listings, send them a connection request."),

    ("Listings", "Posting a gig (Freelancers)",
     "From your home feed, tap Post a gig. Fill in title, description, category, price, and delivery time. "
     "Freelancers can choose to price in their local currency or USD."),
    ("Listings", "Posting a product (Vendors)",
     "Tap Post a product. At least one photo is required. Fill in title, description, category, price, condition "
     "(new/used), and stock quantity."),
    ("Listings", "Posting a request (Buyers)",
     "Tap Post a request to describe what you're looking for — a service or product, with your budget and an "
     "optional deadline. Freelancers and Vendors can see and respond to it."),
    ("Listings", "Editing or deleting a listing",
     "Open your listing and tap Edit listing or Delete listing. Only the original poster can make changes."),
    ("Listings", "Marking a product as sold",
     "On your product listing, tap Mark as sold. This hides it from active search after a short grace period."),

    ("Messaging", "Starting a conversation",
     "Tap Message seller (or Send proposal on a request) from any listing page to start a conversation in your Inbox."),
    ("Messaging", "Sending images in chat",
     "In any conversation, tap the image icon next to the message box to send a photo (max 8MB)."),

    ("Ratings", "How ratings work",
     "Buyers can rate completed transactions, which appear as a star rating and review count on listings and profiles."),

    ("Discovery", "Browse and Search",
     "Browse shows a personalized feed based on your role and interests. Search lets you filter by category, "
     "price range, and rating."),
    ("Discovery", "How the 'For you' feed works",
     "Your 'For you' feed is ranked by matching listing categories to your own profile categories and past activity "
     "(views and messages), with a boost for listings from your connections when they also match your interests."),

    ("Notifications", "Managing notification preferences",
     "Go to Settings > Notifications to toggle Messages, Announcements, and Listing activity notifications on or off."),

    ("Privacy", "What CREET collects",
     "We collect your name, username, email, and profile details you choose to add. We never sell your personal data."),
    ("Privacy", "Blocking a user",
     "On someone's profile, tap the menu (···) and select Block user. Blocked users can't message or view your listings."),
    ("Privacy", "Hiding your online status",
     "Go to Settings > Account to toggle 'Hide online status' so other users can't see when you're active."),

    ("Safety & Reporting", "Reporting a user or listing",
     "Tap the Report link on any profile or listing page, choose a reason, and submit. Reports are reviewed and "
     "repeated or severe reports can lead to automatic suspension."),

    ("Platform Rules", "Terms of Service summary",
     "Each account is tied to one role. You're responsible for the accuracy of your listings and communications. "
     "CREET can review, approve, reject, or remove content that violates these terms."),

    ("Payments", "How CREET Premium payments work",
     "Premium is charged through Flutterwave, in your local currency when supported, or USD otherwise. "
     "Plans are Monthly, 3 Months, or Yearly."),
    ("Payments", "Transactions between buyers and sellers",
     "CREET does not currently process payments for ordinary marketplace transactions between buyers and sellers — "
     "those are arranged directly between the parties via the messaging system."),

    ("Troubleshooting", "App feels slow or won't load",
     "Try closing and reopening the app, or refreshing the page. If the issue continues, check your internet "
     "connection. If it still doesn't resolve, contact support."),
    ("Troubleshooting", "Not receiving email codes",
     "Check your spam folder. You can request a new code from the verification screen. If codes still don't arrive "
     "after a few minutes, contact support."),

    ("Frequently Asked Questions", "Can I have more than one role?",
     "No — each account is tied to exactly one role (Buyer, Freelancer, or Vendor). You'd need a separate account "
     "with a different email to use a different role."),
    ("Frequently Asked Questions", "Is CREET available outside Nigeria?",
     "Yes — CREET supports multiple countries and currencies. Your currency is based on your account's country, "
     "and sellers can choose to price in local currency or USD."),
]


def run():
    db = SessionLocal()
    try:
        added = 0
        for category, title, content in ARTICLES:
            exists = db.query(models.KnowledgeArticle).filter(models.KnowledgeArticle.title == title).first()
            if exists:
                continue
            db.add(models.KnowledgeArticle(category=category, title=title, content=content))
            added += 1
        db.commit()
        print(f"Added {added} articles ({len(ARTICLES) - added} already existed).")
    finally:
        db.close()


if __name__ == "__main__":
    run()
