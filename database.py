import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

class Database:
    def __init__(self, cred_path: str):
        """Initialize Firebase Firestore connection."""
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)

        self.db = firestore.client()
        self.collection = self.db.collection("products")

    def insert(self, data: tuple):
        """
        Insert or update a product record in Firestore.
        If the title exists, add a new timestamped price in the 'history' subcollection.
        :param data: Tuple (title, price, rating, retailer, url)
        """
        title, price, rating, retailer, url = data
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Check if product with the same title already exists
        docs = self.collection.where("title", "==", title).stream()
        existing_doc = None
        for doc in docs:
            existing_doc = doc
            break

        if existing_doc:
            doc_ref = self.collection.document(existing_doc.id)
            # Update main product info (latest price, rating, etc.)
            doc_ref.update({
                "price": price,
                "rating": rating,
                "retailer": retailer,
                "url": url,
                "last_updated": current_time
            })
            # Add price history in subcollection
            doc_ref.collection("history").add({
                "price": price,
                "timestamp": current_time
            })
            print(f"Updated product '{title}' with new price and timestamp.")
        else:
            # Create new product document
            doc_ref = self.collection.add({
                "title": title,
                "price": price,
                "rating": rating,
                "retailer": retailer,
                "url": url,
                "timestamp": current_time,
                "last_updated": current_time
            })[1]  # Firestore returns (update_time, document_reference)
            # Initialize history subcollection
            doc_ref.collection("history").add({
                "price": price,
                "timestamp": current_time
            })
            print(f"Inserted new product '{title}'.")

    def close(self):
        """Firestore does not require closing."""
        pass
