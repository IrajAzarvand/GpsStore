from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Custom authentication backend that allows login with either username or email
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        import logging
        logger = logging.getLogger(__name__)

        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)

        if username is None or password is None:
            logger.warning(f"Authentication failed: missing username or password. Request path: {request.path if request else 'N/A'}")
            return None

        try:
            # Try to fetch user by username or email
            user = User.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
            logger.info(f"User found for authentication: {user.username}, is_staff: {user.is_staff}, is_superuser: {user.is_superuser}, path: {request.path if request else 'N/A'}")
        except User.DoesNotExist:
            logger.warning(f"Authentication failed: user not found for {username}, path: {request.path if request else 'N/A'}")
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a nonexistent user (#20760).
            User().set_password(password)
        else:
            if user.check_password(password) and self.user_can_authenticate(user):
                logger.info(f"Authentication successful for {user.username}, path: {request.path if request else 'N/A'}")
                return user
            else:
                logger.warning(f"Authentication failed: invalid password or inactive user for {user.username}, path: {request.path if request else 'N/A'}")

        return None