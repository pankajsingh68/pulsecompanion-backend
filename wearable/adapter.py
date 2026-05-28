"""Wearable device adapter - PLACEHOLDER for future Samsung Health SDK integration.

This module will eventually handle:
- Samsung Health SDK data ingestion
- Real-time biometric signal processing
- Heart rate and HRV data normalization
- Connection management with wearable devices

Currently returns mock/default values.
"""


def get_biometric_data(device_id: str) -> dict | None:
    """Placeholder: Get biometric data from a wearable device.
    
    Args:
        device_id: The wearable device identifier.
        
    Returns:
        None (not implemented yet).
    """
    # TODO: Implement Samsung Health SDK integration
    return None


def is_device_connected(device_id: str) -> bool:
    """Placeholder: Check if a wearable device is connected.
    
    Args:
        device_id: The wearable device identifier.
        
    Returns:
        False (not implemented yet).
    """
    # TODO: Implement device connection check
    return False


def normalize_heart_rate(raw_hr: int) -> dict:
    """Placeholder: Normalize raw heart rate data.
    
    Args:
        raw_hr: Raw heart rate value from device.
        
    Returns:
        Dict with normalized biometric hint format.
    """
    # TODO: Implement proper normalization
    return {"hr": raw_hr, "hrv": 50}  # Default HRV
