import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional

import requests
from django.conf import settings
from django.utils import timezone as django_timezone

from .models import PaymentInvoice, Profile, Subscription

logger = logging.getLogger(__name__)


class CoinPaymentService:
    """Service class for interacting with NodeJS Coin Payment API."""

    def __init__(self):
        self._base_url = "https://coin-payment.m-gh.com"
        self._api_secret = settings.COIN_PAYMENT_API_SECRET
        self.timeout = 30

    def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict] = None
    ) -> Dict:
        """Make HTTP request to payment service."""
        url = f"{self._base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
        }

        if self._api_secret:
            headers["Authorization"] = f"Bearer {self._api_secret}"

        try:
            if method.upper() == "GET":
                response = requests.get(
                    url, headers=headers, timeout=self.timeout, params=data
                )
            elif method.upper() == "POST":
                response = requests.post(
                    url, headers=headers, json=data, timeout=self.timeout
                )
            else:
                raise Exception(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise Exception(f"Payment service request failed: {str(e)}")
        except ValueError as e:
            raise Exception(f"Invalid JSON response: {str(e)}")

    def create_invoice(
        self,
        profile: Profile,
        subscription: Subscription,
        price_amount: Decimal,
        price_currency: str = "USD",
        success_url: str = None,
        cancel_url: str = None,
        failure_url: str = None,
    ) -> PaymentInvoice:
        """Create a payment invoice for a subscription."""

        # Generate unique order ID
        order_id = f"sub_{subscription.id}_{uuid.uuid4().hex[:8]}"

        # Prepare invoice data
        invoice_data = {
            "priceAmount": float(price_amount),
            "priceCurrency": price_currency,
            "orderId": order_id,
            "orderDescription": f"Subscription: {subscription.plan.name} ({subscription.plan.get_plan_type_display()})",
            "customerEmail": profile.user.email,
        }

        # Add redirect URLs if provided
        if success_url:
            invoice_data["successUrl"] = success_url
        if cancel_url:
            invoice_data["cancelUrl"] = cancel_url
        if failure_url:
            invoice_data["failureUrl"] = failure_url

        # Make API request
        response_data = self._make_request(
            "POST", "/api/payment/create-invoice", invoice_data
        )

        if not response_data.get("success"):
            raise Exception(
                f"Failed to create invoice: {response_data.get('message', 'Unknown error')}"
            )

        invoice_info = response_data.get("data", {})

        # Parse expiration date
        expires_at = None
        if invoice_info.get("expiresAt"):
            try:
                expires_at = datetime.fromisoformat(
                    invoice_info["expiresAt"].replace("Z", "+00:00")
                ).replace(tzinfo=django_timezone.utc)
            except (ValueError, TypeError):
                pass

        # Create PaymentInvoice record
        payment_invoice = PaymentInvoice.objects.create(
            profile=profile,
            subscription=subscription,
            order_id=order_id,
            invoice_id=invoice_info.get("invoiceId"),
            payment_url=invoice_info.get("paymentUrl"),
            price_amount=price_amount,
            price_currency=price_currency,
            pay_amount=invoice_info.get("payAmount"),
            pay_currency=invoice_info.get("payCurrency"),
            status=invoice_info.get("status", "waiting"),
            expires_at=expires_at,
            customer_email=profile.user.email,
            order_description=invoice_data["orderDescription"],
            metadata={
                "subscription_plan_id": subscription.plan.id,
                "subscription_plan_name": subscription.plan.name,
                "created_via_api": True,
            },
        )

        return payment_invoice

    def get_invoice_status(self, order_id: str) -> Dict:
        """Get invoice status by order ID."""
        response_data = self._make_request(
            "GET", "/api/payment/invoices", {"orderId": order_id}
        )
        logger.info(f"Response data for get invoice status: {response_data}")

        return response_data

    def process_webhook_data(self, webhook_data: Dict) -> bool:
        """Process webhook data from payment service."""
        logger.info(f"Processing webhook data: {webhook_data}")
        try:
            order_id = webhook_data.get("order_id")
            if not order_id:
                return False

            # Find the corresponding payment invoice
            try:
                payment_invoice = PaymentInvoice.objects.get(order_id=order_id)
            except Exception:
                return False

            # Update payment invoice with webhook data
            payment_invoice.invoice_id = webhook_data.get(
                "invoice_id", payment_invoice.invoice_id
            )
            payment_invoice.status = webhook_data.get("status", payment_invoice.status)
            payment_invoice.pay_amount = webhook_data.get(
                "pay_amount", payment_invoice.pay_amount
            )
            payment_invoice.pay_currency = webhook_data.get(
                "pay_currency", payment_invoice.pay_currency
            )
            payment_invoice.actually_paid = webhook_data.get(
                "actually_paid", payment_invoice.actually_paid
            )
            payment_invoice.actually_paid_at_fiat = webhook_data.get(
                "actually_paid_at_fiat", payment_invoice.actually_paid_at_fiat
            )
            payment_invoice.purchase_id = webhook_data.get(
                "purchase_id", payment_invoice.purchase_id
            )

            # Update metadata
            payment_invoice.metadata.update(
                {
                    "webhook_received_at": django_timezone.now().isoformat(),
                    "webhook_data": webhook_data,
                }
            )

            # If payment is finished, mark as paid and activate subscription
            if webhook_data.get("status") == "finished":
                payment_invoice.paid_at = django_timezone.now()

                # Activate the subscription
                if payment_invoice.subscription:
                    payment_invoice.subscription.activate()

                    # Update subscription payment reference
                    payment_invoice.subscription.payment_reference = (
                        payment_invoice.purchase_id or payment_invoice.invoice_id
                    )
                    payment_invoice.subscription.save()

            payment_invoice.save()
            return True

        except Exception as e:
            # Log the error but don't raise it to avoid webhook failures
            print(f"Error processing webhook data: {str(e)}")
            return False


# Singleton instance
payment_service = CoinPaymentService()
