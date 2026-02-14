from collections.abc import Iterable, Sequence
from typing import Any


class SourceArgumentExceptionMultiple(Exception):
    """Error base class for errors associated with multiple arguments."""

    def __init__(self, arguments: Iterable[str], message: str) -> None:
        """Initialize the SourceArgumentExceptionMultiple.

        Args:
            arguments (Iterable[str]): an iterable of arguments the source arguments (written exactly like in the source __init__).
            message (str): Message to be displayed for all provided arguments.
        """
        self._arguments = arguments
        self.message = message
        super().__init__(self.message)

    @property
    def arguments(self) -> Iterable[str]:
        return self._arguments


class SourceArgumentException(Exception):
    def __init__(self, argument: str, message: str) -> None:
        """Initialize the SourceArgumentException.

        Args:
            argument (str): The source argument that caused the exception (written exactly like in the source __init__).
            message (str): Message to be displayed for the provided argument.
        """
        self._argument = argument
        self.message = message
        super().__init__(self.message)

    @property
    def argument(self) -> str:
        return self._argument


class SourceArgumentSuggestionsExceptionBase(SourceArgumentException):
    """Base class for exceptions that provide suggestions for a source argument."""

    def __init__(
        self,
        argument: str,
        message: str,
        suggestions: Iterable[object],
        message_addition: str = "",
    ):
        """Initialize the SourceArgumentSuggestionsExceptionBase.

        Args:
            argument (str): The source argument that caused the exception (written exactly like in the source __init__).
            message (str): Message to be displayed for the provided argument.
            suggestions (Iterable[T]): An iterable of suggestions for the provided argument.
            message_addition (str, optional): Additional message appended after the main message adding additional information. Defaults to "".
        """
        self._simple_message = message
        message += f", {message_addition}" if message_addition else ""
        super().__init__(argument=argument, message=message)
        self._suggestions = list(suggestions)
        self._suggestion_type: type[object] | None = type(self._suggestions[0]) if self._suggestions else None

    @property
    def suggestions(self) -> Sequence[object]:
        return self._suggestions

    @property
    def suggestion_type(self) -> type[object] | None:
        return self._suggestion_type

    @property
    def simple_message(self) -> str:
        return self._simple_message


class SourceArgumentNotFound(SourceArgumentException):
    """Invalid source arguments provided."""

    def __init__(
        self,
        argument: str,
        value: Any,
        message_addition="please check the spelling and try again.",
    ) -> None:
        """Initialize the SourceArgumentNotFound.

        Args:
            argument (str): The source argument that caused the exception (written exactly like in the source __init__).
            value (Any): The value of that source argument.
            message_addition (str, optional): Additional message information. Defaults to "please check the spelling and try again.".
        """
        self._simple_message = f"We could not find values for the argument '{argument}' with the value '{value}'"
        self.message = self._simple_message
        if message_addition:
            self.message += f", {message_addition}"
        super().__init__(argument, self.message)

    @property
    def simple_message(self) -> str:
        return self._simple_message


class SourceArgumentNotFoundWithSuggestions(SourceArgumentSuggestionsExceptionBase):
    """Invalid source arguments provided but suggestions provided.

    This should be raised if a source argument is not valid but you want to provide suggestions to the user what they could use instead.
    """

    def __init__(self, argument: str, value: Any, suggestions: Iterable[object]) -> None:
        """Initialize the SourceArgumentNotFoundWithSuggestions.

        Args:
            argument (str): The source argument that caused the exception (written exactly like in the source __init__).
            value (Any): The value of that source argument.
            suggestions (Iterable[T]): An iterable of suggestions for the provided argument.
        """
        message = f"We could not find values for the argument '{argument}' with the value '{value}'"
        suggestions = list(suggestions)
        if len(suggestions) == 0:
            message += ", We could not find any suggestions. Please also check other arguments."
            message_addition = ""
        else:
            message_addition = f"you may want to use one of the following: {suggestions}"
        super().__init__(
            argument=argument,
            message=message,
            message_addition=message_addition,
            suggestions=suggestions,
        )


class SourceArgAmbiguousWithSuggestions(SourceArgumentSuggestionsExceptionBase):
    """Multiple values found for the argument with suggestions provided.

    This should be raised if a there are multiple different results matching the source argument and you want to provide suggestions to the user what they could use instead.
    """

    def __init__(self, argument: str, value: Any, suggestions: Iterable[object]) -> None:
        """Initialize the SourceArgAmbiguousWithSuggestions.

        Args:
            argument (str): The source argument that caused the exception (written exactly like in the source __init__).
            value (Any): The value of that source argument.
            suggestions (Iterable[object]): An iterable of suggestions for the provided argument.
        """
        message = f"Multiple values found for the argument '{argument}' with the value '{value}'"
        message_addition = f"please specify one of: {suggestions}"
        super().__init__(
            argument=argument,
            message=message,
            suggestions=suggestions,
            message_addition=message_addition,
        )


class SourceArgumentRequired(SourceArgumentException):
    """Argument must be provided.

    This should be raised if a source argument is required but not provided by the user.
    """

    def __init__(self, argument: str, reason: str) -> None:
        """Initialize the SourceArgumentRequired.

        Args:
            argument (str): The source argument that is required but not provided (written exactly like in the source __init__).
            reason (str): The reason why the source argument is required.
        """
        self.message = f"Argument '{argument}' must be provided"
        if reason:
            self.message += f", {reason}"
        super().__init__(argument, self.message)


class SourceArgumentRequiredWithSuggestions(SourceArgumentSuggestionsExceptionBase):
    """Argument must be provided.

    This should be raised if a source argument is required but not provided by the user and you want to provide suggestions to the user what they could use.
    """

    def __init__(self, argument: str, reason: str, suggestions: Iterable[object]) -> None:
        """Initialize the SourceArgumentRequiredWithSuggestions.

        Args:
            argument (str): The source argument that is required but not provided (written exactly like in the source __init__).
            reason (str): The reason why the source argument is required.
            suggestions (Iterable[object]): An iterable of suggestions for the provided argument.
        """
        message = f"Argument '{argument}' must be provided"
        message_addition = f"you may want to use one of the following: {list(suggestions)}"
        if reason:
            message += f", {reason}"
        super().__init__(
            argument=argument,
            message=message,
            message_addition=message_addition,
            suggestions=suggestions,
        )
