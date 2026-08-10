import aiohttp
import logging
import json

logger = logging.getLogger(__name__)

class LTCVerifier:
    """
    Litecoin transaction verifier supporting multiple fallback APIs.
    """

    @staticmethod
    def is_valid_txid_format(txid: str) -> bool:
        txid = txid.strip()
        return len(txid) == 64 and all(c in "0123456789abcdefABCDEF" for c in txid)

    @classmethod
    async def verify_transaction(cls, txid: str, expected_address: str, expected_amount_ltc: float):
        txid = txid.strip().lower()
        expected_address = expected_address.strip()
        
        if not cls.is_valid_txid_format(txid):
            return False, 0.0, "Invalid TXID format. A Litecoin TXID must be a 64-character hexadecimal hash."

        # Convert expected amount in LTC to satoshis (1 LTC = 100,000,000 satoshis)
        expected_satoshis = int(round(expected_amount_ltc * 100_000_000))
        # Allow tiny float rounding tolerance (99.9% of expected)
        min_required_satoshis = int(expected_satoshis * 0.999)

        # 1. Try BlockCypher API
        success, amount_found, msg = await cls._check_blockcypher(txid, expected_address, min_required_satoshis)
        if success:
            return True, amount_found, msg
        elif "rate limit" not in msg.lower() and "404" not in msg:
            # If explicit mismatch found on BlockCypher, return
            if "underpaid" in msg.lower() or "address not found" in msg.lower():
                return False, amount_found, msg

        # 2. Fallback to Blockchair API
        success, amount_found, msg_bc = await cls._check_blockchair(txid, expected_address, min_required_satoshis)
        if success:
            return True, amount_found, msg_bc

        # Combine messages if neither succeeded
        return False, amount_found, msg if msg else msg_bc

    @classmethod
    async def _check_blockcypher(cls, txid: str, expected_address: str, min_required_satoshis: int):
        url = f"https://api.blockcypher.com/v1/ltc/main/txs/{txid}"
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(url) as resp:
                    if resp.status == 404:
                        return False, 0.0, "Transaction ID not found on Litecoin network yet. Please wait a moment for propagation."
                    if resp.status == 429:
                        return False, 0.0, "BlockCypher rate limit hit, trying secondary provider..."
                    if resp.status != 200:
                        return False, 0.0, f"Blockchain provider returned status code {resp.status}."

                    data = await resp.json()
                    outputs = data.get("outputs", [])
                    
                    received_satoshis = 0
                    for out in outputs:
                        addresses = out.get("addresses", [])
                        value = out.get("value", 0)
                        for addr in addresses:
                            if addr.lower() == expected_address.lower():
                                received_satoshis += value

                    received_ltc = received_satoshis / 100_000_000.0

                    if received_satoshis == 0:
                        return False, 0.0, f"Transaction found, but target LTC address ({expected_address[:8]}...) received 0 LTC in this transaction."

                    if received_satoshis < min_required_satoshis:
                        return False, received_ltc, f"Underpaid! Received {received_ltc:.6f} LTC, but required amount is {(min_required_satoshis/100_000_000):.6f} LTC."

                    return True, received_ltc, f"Successfully verified! Received {received_ltc:.6f} LTC."

        except Exception as e:
            logger.warning(f"BlockCypher check failed: {e}")
            return False, 0.0, f"Network error checking BlockCypher: {str(e)}"

    @classmethod
    async def _check_blockchair(cls, txid: str, expected_address: str, min_required_satoshis: int):
        url = f"https://api.blockchair.com/litecoin/dashboards/transaction/{txid}"
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(url) as resp:
                    if resp.status == 404:
                        return False, 0.0, "Transaction ID not found on Litecoin network."
                    if resp.status != 200:
                        return False, 0.0, f"Blockchair API returned HTTP {resp.status}."

                    data = await resp.json()
                    tx_data = data.get("data", {}).get(txid, {})
                    outputs = tx_data.get("outputs", [])

                    received_satoshis = 0
                    for out in outputs:
                        recipient = out.get("recipient", "")
                        value = out.get("value", 0)
                        if recipient.lower() == expected_address.lower():
                            received_satoshis += value

                    received_ltc = received_satoshis / 100_000_000.0

                    if received_satoshis == 0:
                        return False, 0.0, f"Transaction found, but expected LTC address was not a recipient."

                    if received_satoshis < min_required_satoshis:
                        return False, received_ltc, f"Underpaid! Received {received_ltc:.6f} LTC, but required amount is {(min_required_satoshis/100_000_000):.6f} LTC."

                    return True, received_ltc, f"Successfully verified! Received {received_ltc:.6f} LTC."

        except Exception as e:
            logger.warning(f"Blockchair check failed: {e}")
            return False, 0.0, f"Network error checking Blockchair: {str(e)}"
