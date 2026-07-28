"""Tests for digital product storefront."""
import pytest
from aeloria.commerce.storefront import Storefront, Product, Purchase


class TestProductDefaults:
    def test_auto_timestamp(self):
        p = Product(product_id="test", name="Test Product", price=19.00)
        assert p.created_at  # non-empty

    def test_defaults(self):
        p = Product(product_id="test")
        assert p.currency == "usd"
        assert p.active is True
        assert p.type == "digital"


class TestStorefront:
    def test_loads_default_products(self):
        store = Storefront()
        products = store.list_products()
        assert len(products) >= 3
        assert any(p.product_id == "prompt-pack-v1" for p in products)

    def test_get_product(self):
        store = Storefront()
        product = store.get_product("prompt-pack-v1")
        assert product is not None
        assert product.name == "AI Prompt Pack vol. 1"
        assert product.price == 19.00

    def test_get_nonexistent_product(self):
        store = Storefront()
        assert store.get_product("nonexistent") is None

    def test_list_active_only(self):
        store = Storefront()
        # Deactivate a product
        store._products["prompt-pack-v1"].active = False
        active = store.list_products(active_only=True)
        assert all(p.active for p in active)
        assert "prompt-pack-v1" not in [p.product_id for p in active]
        # Restore
        store._products["prompt-pack-v1"].active = True

    def test_add_product(self):
        store = Storefront()
        new_product = Product(product_id="new-pack", name="New Pack", price=29.00)
        store.add_product(new_product)
        assert store.get_product("new-pack") is not None


class TestCreateCheckout:
    def test_returns_url(self):
        store = Storefront()
        product = store.get_product("prompt-pack-v1")
        url = store.create_checkout(product, "user@example.com")
        assert "checkout" in url.lower()
        assert "user@example.com" in url or "prompt-pack-v1" in url

    def test_mock_url_without_stripe(self):
        store = Storefront()  # no stripe_secret_key
        product = store.get_product("workflow-templates")
        url = store.create_checkout(product, "buyer@test.com")
        assert "mock" in url or "checkout" in url


class TestProcessWebhook:
    def test_successful_purchase(self):
        store = Storefront()
        event = {
            "product_id": "prompt-pack-v1",
            "customer_email": "buyer@example.com",
            "amount_total": 1900,  # cents
            "session_id": "sess-123",
        }
        purchase = store.process_webhook(event)
        assert purchase.status == "paid"
        assert purchase.customer_email == "buyer@example.com"
        assert purchase.amount == 19.00  # converted from cents
        assert purchase.download_url  # has delivery URL

    def test_failed_purchase_unknown_product(self):
        store = Storefront()
        event = {
            "product_id": "nonexistent",
            "customer_email": "user@test.com",
            "amount_total": 100,
            "session_id": "sess-456",
        }
        purchase = store.process_webhook(event)
        assert purchase.status == "failed"
        assert purchase.download_url == ""


class TestRevenueSummary:
    def test_empty_purchases(self):
        store = Storefront()
        summary = store.revenue_summary([])
        assert summary["total_revenue"] == 0
        assert summary["total_purchases"] == 0

    def test_calculates_revenue(self):
        store = Storefront()
        purchases = [
            Purchase(product_id="a", amount=19.00, status="paid"),
            Purchase(product_id="b", amount=49.00, status="paid"),
            Purchase(product_id="c", amount=99.00, status="refunded"),  # not counted
        ]
        summary = store.revenue_summary(purchases)
        assert summary["total_revenue"] == 68.00
        assert summary["total_purchases"] == 2  # only paid
        assert summary["revenue_by_product"]["a"] == 19.00
        assert "c" not in summary["revenue_by_product"]  # refunded excluded

    def test_avg_order_value(self):
        store = Storefront()
        purchases = [
            Purchase(product_id="a", amount=20.00, status="paid"),
            Purchase(product_id="b", amount=40.00, status="paid"),
        ]
        summary = store.revenue_summary(purchases)
        assert summary["avg_order_value"] == 30.00