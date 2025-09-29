import sys

# Mock imghdr module to bypass import
class MockImghdr:
    def what(self, *args, **kwargs):
        return None  # Return None to skip image validation

sys.modules['imghdr'] = MockImghdr()