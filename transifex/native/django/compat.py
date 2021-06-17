try:
    from django.template.base import (TOKEN_BLOCK, TOKEN_COMMENT,
                                      TOKEN_TEXT, TOKEN_VAR)
except ImportError:
    from django.template.base import TokenType
    TOKEN_BLOCK = TokenType.BLOCK
    TOKEN_COMMENT = TokenType.COMMENT
    TOKEN_TEXT = TokenType.TEXT
    TOKEN_VAR = TokenType.VAR
