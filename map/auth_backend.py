from django.contrib.auth.backends import ModelBackend
from .roles import is_admin

class RoleBackend(ModelBackend):
    def has_perm(self, user_obj, perm, obj=None):
        return is_admin(user_obj) or super().has_perm(user_obj, perm, obj)
    def has_module_perms(self, user_obj, app_label):
        return is_admin(user_obj) or super().has_module_perms(user_obj, app_label)
