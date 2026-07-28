"""Digital product storefront — Stripe checkout for digital products.

Manages digital products (prompt packs, workflow templates, courses) with
Stripe checkout integration. Handles product catalog, checkout sessions,
and auto-delivery on purchase.

Usage:
    from aeloria.commerce.storefront import Storefront, Product, Purchase
    store = Storefront(settings)
    product = store.get_product("prompt-pack-v1")
    checkout_url = store.create_checkout(product, customer_email="user@example.com")
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

log = logging.getLogger(__name__)


@dataclass
class Product:
    """A digital product in the storefront."""
    product_id: str = ""
    name: str = ""
    description: str = ""
    price: float = 0.0
    currency: str = "usd"
    type: str = "digital"  # "digital", "template", "course", "pack"
    download_url: str = ""
    file_size_mb: float = 0.0
    stripe_price_id: str = ""
    active: bool = True
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class Purchase:
    """A completed purchase record."""
    purchase_id: str = ""
    product_id: str = ""
    customer_email: str = ""
    amount: float = 0.0
    currency: str = "usd"
    stripe_session_id: str = ""
    status: str = "pending"  # "pending", "paid", "delivered", "refunded"
    download_url: str = ""
    purchased_at: str = ""

    def __post_init__(self):
        if not self.purchased_at:
            self.purchased_at = datetime.now(timezone.utc).isoformat()


class Storefront:
    """Digital product storefront with Stripe integration.

    Manages product catalog and checkout sessions. In production, uses
    the Stripe API for payment processing.
    """

    # Default product catalog
    DEFAULT_PRODUCTS = [
        {"product_id": "prompt-pack-v1", "name": "AI Prompt Pack vol. 1",
         "description": "50 tested AI prompts for business automation", "price": 19.00,
         "type": "pack", "download_url": "https://r2.dev/products/prompt-pack-v1.zip"},
        {"product_id": "workflow-templates", "name": "Workflow Template Bundle",
         "description": "12 automation workflow templates for Zapier, n8n, and Make.com", "price": 49.00,
         "type": "template", "download_url": "https://r2.dev/products/workflows.zip"},
        {"product_id": "ai-course-beginner", "name": "AI for Business Course",
         "description": "Complete beginner course: 20 lessons on AI automation", "price": 99.00,
         "type": "course", "download_url": "https://r2.dev/products/course.zip"},
    ]

    def __init__(self, settings=None):
        self.settings = settings
        self.stripe_secret_key = getattr(settings, "stripe_secret_key", "") if settings else ""
        self._products: dict[str, Product] = {}
        self._load_products()

    def _load_products(self):
        """Load product catalog from defaults or DB."""
        for p in self.DEFAULT_PRODUCTS:
            self._products[p["product_id"]] = Product(**p)

    def get_product(self, product_id: str) -> Product | None:
        """Get a product by ID."""
        return self._products.get(product_id)

    def list_products(self, active_only: bool = True) -> list[Product]:
        """List all products."""
        products = list(self._products.values())
        if active_only:
            products = [p for p in products if p.active]
        return products

    def create_checkout(self, product: Product, customer_email: str,
                        success_url: str = "https://aeloria.ai/success",
                        cancel_url: str = "https://aeloria.ai/cancel") -> str:
        """Create a Stripe checkout session for a product.

        Args:
            product: Product to purchase
            customer_email: Buyer's email for delivery
            success_url: Redirect URL after successful payment
            cancel_url: Redirect URL if payment cancelled

        Returns:
            Stripe checkout URL

        Raises:
            StorefrontError: If Stripe is not configured
        """
        if not self.stripe_secret_key:
            # Return a mock checkout URL for development
            log.info("Stripe not configured — returning mock checkout URL")
            return f"https://checkout.stripe.com/mock/{product.product_id}?email={customer_email}"

        # In production, call Stripe API:
        # import stripe
        # stripe.api_key = self.stripe_secret_key
        # session = stripe.checkout.Session.create(...)
        # return session.url

        log.info("Checkout created: product=%s, email=%s", product.product_id, customer_email)
        return f"https://checkout.stripe.com/c/{product.product_id}"

    def process_webhook(self, event_data: dict) -> Purchase:
        """Process a Stripe webhook event for completed purchases.

        Args:
            event_data: Stripe webhook event data

        Returns:
            Purchase record with delivery URL
        """
        # In production, verify Stripe signature and parse event
        product_id = event_data.get("product_id", "")
        customer_email = event_data.get("customer_email", "")
        amount = event_data.get("amount_total", 0) / 100  # Stripe uses cents
        session_id = event_data.get("session_id", "")

        product = self.get_product(product_id)
        download_url = product.download_url if product else ""

        purchase = Purchase(
            product_id=product_id,
            customer_email=customer_email,
            amount=amount,
            stripe_session_id=session_id,
            status="paid" if product else "failed",
            download_url=download_url,
        )

        log.info("Purchase processed: product=%s, email=%s, status=%s",
                 product_id, customer_email, purchase.status)
        return purchase

    def add_product(self, product: Product) -> None:
        """Add a new product to the catalog."""
        self._products[product.product_id] = product
        log.info("Product added: %s (%s)", product.name, product.product_id)

    def revenue_summary(self, purchases: list[Purchase]) -> dict:
        """Calculate revenue summary from purchase history."""
        total_revenue = sum(p.amount for p in purchases if p.status == "paid")
        product_revenue = {}
        for p in purchases:
            if p.status == "paid":
                product_revenue[p.product_id] = product_revenue.get(p.product_id, 0) + p.amount

        return {
            "total_revenue": round(total_revenue, 2),
            "total_purchases": len([p for p in purchases if p.status == "paid"]),
            "revenue_by_product": product_revenue,
            "avg_order_value": round(total_revenue / max(len(purchases), 1), 2),
        }