from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Bech32 human-readable prefix of BOLT11 invoices per network.
INVOICE_PREFIX = {
    "regtest": "lnbcrt",
    "signet": "lntbs",
    "testnet": "lntb",
    "mainnet": "lnbc",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOUTIK_", extra="ignore")

    network: Literal["regtest", "signet", "testnet"] = "regtest"
    demo_mode: bool = False
    shop_name: str = Field("Ma Boutique", max_length=60)
    # Optional initial PIN. When empty the PWA asks the merchant to create one.
    pin: str = ""
    # Base URL for ardoise links. Empty = derived from the request (works on a LAN IP too).
    public_url: str = ""
    cookie_secure: bool = True

    data_dir: Path = Path("/data")
    creds_dir: Path = Path("/creds")
    lnd_merchant_url: str = "https://lnd-merchant:8080"
    lnd_customer_url: str = "https://lnd-customer:8080"

    # "auto" = live BTC/EUR from public APIs with a fixed fallback; "fixed" = never call out.
    rate_source: Literal["auto", "fixed"] = "auto"
    fallback_eur_per_btc: float = 90_000.0

    assistant_model: str = "claude-opus-5-5"
    anthropic_api_key: str = Field("", validation_alias="ANTHROPIC_API_KEY")

    # Guard rails.
    max_invoice_xof: int = 2_000_000
    min_invoice_xof: int = 25
    daily_send_limit_xof: int = 100_000
    sale_invoice_expiry_s: int = 900
    session_ttl_s: int = 12 * 3600

    @property
    def invoice_prefix(self) -> str:
        return INVOICE_PREFIX[self.network]

    @property
    def db_path(self) -> Path:
        return self.data_dir / "boutik.sqlite3"


@lru_cache
def get_settings() -> Settings:
    return Settings()
