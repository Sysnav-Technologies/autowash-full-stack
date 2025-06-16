# Create a new file: apps/core/serializers.py

import json
import uuid
from decimal import Decimal
from django.contrib.sessions.serializers import JSONSerializer
from django.core.serializers.json import DjangoJSONEncoder


class UUIDJSONEncoder(DjangoJSONEncoder):
    """
    Custom JSON encoder that handles UUID objects and other Django types
    """
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class UUIDSafeJSONSerializer(JSONSerializer):
    """
    Custom session serializer that can handle UUID objects
    """
    def dumps(self, obj):
        return json.dumps(obj, separators=(',', ':'), cls=UUIDJSONEncoder).encode('latin-1')
    
    def loads(self, data):
        return json.loads(data.decode('latin-1'))