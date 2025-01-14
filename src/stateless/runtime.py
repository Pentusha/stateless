"""Runtime for executing effects."""

from dataclasses import dataclass
from functools import cache
from typing import Generic, Literal, Tuple, Type, TypeVar, cast, overload

from stateless.effect import Effect
from stateless.errors import MissingAbilityError
from stateless.parallel import Parallel

A = TypeVar("A")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
R = TypeVar("R")
E = TypeVar("E", bound=Exception)


@cache
def _get_ability(ability_type: Type[A], abilities: Tuple[A, ...]) -> A:
    for ability in abilities:
        if isinstance(ability, ability_type):
            return ability
    raise MissingAbilityError(ability_type)


@dataclass(frozen=True)
class Runtime(Generic[A]):
    """A runtime for executing effects."""

    abilities: tuple[A, ...] = ()

    def use(self, ability: A2) -> "Runtime[A | A2]":
        """
        Use an ability with this runtime.

        Enables running effects that require the ability.

        Args:
        ----
            ability: The ability to use.

        Returns:
        -------
            A new runtime with the ability.
        """
        return Runtime((ability, *self.abilities))

    def get_ability(self, ability_type: Type[A]) -> A:
        """
        Get an ability from the runtime.

        Args:
        ----
            ability_type: The type of the ability to get.

        Returns:
        -------
            The ability.
        """

        return _get_ability(ability_type, self.abilities)  # type: ignore

    @overload
    def run(self, effect: Effect[A, E, R], return_errors: Literal[False] = False) -> R:
        ...

    @overload
    def run(
        self, effect: Effect[A, E, R], return_errors: Literal[True] = True
    ) -> R | E:
        ...

    def run(self, effect: Effect[A, E, R], return_errors: bool = False) -> R | E:
        """
        Run an effect.

        Args:
        ----
            effect: The effect to run.
            return_errors: Whether to return errors yielded by the effect.

        Returns:
        -------
            The result of the effect.
        """
        try:
            ability_or_error = next(effect)

            while True:
                try:
                    match ability_or_error:
                        case None:
                            ability_or_error = effect.send(None)
                        case Exception() as error:
                            try:
                                ability_or_error = effect.throw(error)
                            except type(error) as e:
                                if return_errors and e is error:
                                    return cast(E, e)
                                raise e
                        case ability_type if ability_type is Parallel:
                            ability_or_error = effect.send(self)
                        case ability_type:
                            ability = self.get_ability(ability_type)
                            ability_or_error = effect.send(ability)
                except MissingAbilityError as error:
                    ability_or_error = effect.throw(error)
        except StopIteration as e:
            return cast(R, e.value)
