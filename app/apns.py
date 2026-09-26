def send_apns(device_token, title, body, critical=False):
    # APNs integration is intentionally isolated here.
    # Critical alerts require Apple's special entitlement/approval.
    return False, "APNs noch nicht konfiguriert"
