from rest_framework import permissions


class IsAuthor(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):
        ALLOWED_METHODS = ["PATCH", "DELETE", "PUT"]
        return (
            request.method not in ALLOWED_METHODS
            or request.method in ALLOWED_METHODS and obj.author == request.user
        )
