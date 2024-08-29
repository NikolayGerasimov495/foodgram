from rest_framework.response import Response
from rest_framework import status


class CreateDestroyObjectMixin:

    @staticmethod
    def create_object(
            input_serializer,
            serializer_data,
            output_serializer,
            serializer_context=None,
            output_serializer_context=None
    ):
        serializer = input_serializer(
            data=serializer_data,
            context=serializer_context or {}
        )
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(
            output_serializer(obj,
                              context=output_serializer_context or {}).data,
            status=status.HTTP_201_CREATED
        )

    @staticmethod
    def destroy_object(
            input_serializer,
            serializer_data,
            model,
            extra_data,
            serializer_context=None
    ):
        serializer = input_serializer(
            data=serializer_data,
            context=serializer_context or {}
        )
        serializer.is_valid(raise_exception=True)
        model.objects.get(**(serializer_data | extra_data)).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
