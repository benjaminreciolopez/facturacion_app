def get_user_safe(request):
    try:
        return request.session.get("user")
    except Exception:
        return None
