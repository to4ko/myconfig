import re
from typing import List, Union

from pymorphy3 import MorphAnalyzer
from pymorphy3.analyzer import Parse

NUMBERS = """0,ноль,нулевой
1,один,первый
2,два,второй
3,три,третий
4,четыре,четвертый
5,пять,пятый
6,шесть,шестой
7,семь,седьмой
8,восемь,восьмой
9,девять,девятый
10,десять,десятый
11,одиннадцать,одиннадцатый
12,двенадцать,двенадцатый
13,тринадцать,тринадцатый
14,четырнадцать,четырнадцатый
15,пятнадцать,пятнадцатый
16,шестнадцать,шестнадцатый
17,семнадцать,семнадцатый
18,восемнадцать,восемнадцатый
19,девятнадцать,девятнадцатый
20,двадцать,двадцатый
30,тридцать,тридцатый
40,сорок,сороковой
50,пятьдесят,пятидесятый
60,шестьдесят,шестидесятый
70,семьдесят,семидесятый
80,восемьдесят,восьмидесятый
90,девяносто,девяностый
100,сто,сотый
200,двести,двухсотый
300,триста,трехсотый
400,четыреста,четырехсотый
500,пятьсот,пятисотый
600,шестьсот,шестисотый
700,семьсот,семисотый
800,восемьсот,восьмисотый
900,девятьсот,девятисотый
1000,тысяча,тысячный
1000000,миллион,миллионный"""


class MorphNumber:
    def __init__(self):
        self.morph = MorphAnalyzer()

        # создаём словарь из чисел и порядковых числительных
        self.dict = {}
        for i in NUMBERS.split("\n"):
            x, card, ord_ = i.split(",")
            self.dict[int(x)] = card
            self.dict[card] = ord_

    def parse(self, word: str) -> Parse:
        words: List[Parse] = self.morph.parse(word)
        # search first noms
        # https://pymorphy2.readthedocs.io/en/stable/user/grammemes.html?highlight=gent#russian-cases
        for word in words:
            if word.tag.case == "nomn":
                return word
        # return any result
        return words[0]

    def integer_to_words(self, integer: int, text: str = None) -> list[str]:
        """Конвертирует число в текст, опционально согласуя его с текстом после
        числа. Поддерживает только целые числа
        """
        if integer < 0:
            return ["минус"] + self.integer_to_words(-integer, text)

        if integer == 0:
            return ["ноль"]

        # граммемы последней цифры
        if text:
            last_word = text.rsplit(" ", 1)[-1]
            tag = self.parse(last_word).tag
        else:
            tag = None

        hundred = 0
        ten = 0
        words = []

        # номер цифры в числе
        k = len(str(integer)) - 1
        for digit in str(integer):
            digit = int(digit)

            # сотни
            if k % 3 == 2:
                if digit > 0:
                    words.append(self.dict[digit * 100])
                hundred = digit

            # десятки
            elif k % 3 == 1:
                if digit > 1:
                    words.append(self.dict[digit * 10])
                ten = digit

            # тысячи и единицы
            else:
                # десять, одинадцать, двенадцать...
                if ten == 1:
                    digit += 10

                if digit > 0:
                    # тысячи женского рода (только для 1 и 2)
                    # например: одна тысяча, две тысячи
                    if k == 3 and digit <= 2:
                        w: Parse = self.parse(self.dict[digit])
                        w: Parse = w.inflect({"femn"})
                        words.append(w.word)

                    # граммемы последней цифры (только для 1 и 2)
                    # например: один градус, одна задача, одно дерево
                    elif k == 0 and digit <= 2 and tag:
                        w: Parse = self.parse(self.dict[digit])
                        w: Parse = w.inflect({tag.gender, tag.case})
                        # не может согласовать "2 грамма"
                        words.append(w.word if w else self.dict[digit])

                    else:
                        words.append(self.dict[digit])

                # например: сто тысяч, десять миллионов, один миллиард
                if k > 2 and (hundred or ten or digit):
                    w2: Parse = self.parse(self.dict[10**k])
                    w2: Parse = w2.make_agree_with_number(digit)
                    words.append(w2.word)

            k -= 1

        return words

    def float_to_words(self, integer: int, decimal: int, decsize: int) -> list[str]:
        # правильно:   двадцать две целых и две десятых градуса
        # неправильно: двадцать две целые и две десятые градуса
        # неправильно: двадцать два целых и два десятых градуса
        words = self.integer_to_words(integer, "часть")
        words += ["целая" if first(integer) else "целых"]

        words += ["и"]

        words += self.integer_to_words(decimal, "часть")
        if decsize == 1:
            words += ["десятая" if first(integer) else "десятых"]
        elif decsize == 2:
            words += ["сотая" if first(integer) else "сотых"]
        elif decsize == 3:
            words += ["тысячная" if first(integer) else "тысячных"]

        return words

    def words_after_number(self, number: int, text: str) -> list[str]:
        number = abs(number)

        words = []

        for word in text.split(" "):
            w: Parse = self.parse(word)
            grammemes = w.tag.numeral_agreement_grammemes(number)
            if grammemes == {"sing", "accs"}:
                grammemes = {"sing", w.tag.case}
            if w := w.inflect(grammemes):
                words.append(w.word)

        return words

    def number_with_text(
        self, value: Union[int, float, str], text: str, as_text: bool = True
    ) -> str:
        integer, decimal, decsize = parse_number(value)

        if as_text:
            words = (
                self.integer_to_words(integer, text)
                if decimal == 0
                else self.float_to_words(integer, decimal, decsize)
            )
        else:
            # support as_test=None
            words = [str(value)] if as_text is False else []

        if text:
            words += self.words_after_number(integer if decimal == 0 else 2, text)

        return " ".join(words)

    def number_with_custom_text(
        self, value: Union[int, float, str], texts: list[str], as_text: bool = True
    ) -> str:
        integer, decimal, decsize = parse_number(value)

        if first(integer):
            text = texts[0]
        elif second(integer):
            text = texts[1]
        else:
            text = texts[2]

        if as_text:
            words = (
                self.integer_to_words(integer, text)
                if decimal == 0
                else self.float_to_words(integer, decimal, decsize)
            )
        else:
            # support as_test=None
            words = [str(value)] if as_text is False else []

        words += [text if decimal == 0 else texts[1]]

        return " ".join(words)

    def number_to_ordinal(self, number: Union[int, float, str], first_word: str) -> str:
        integer = int(float(number))

        if integer >= 1000:
            return str(number)

        words = self.integer_to_words(integer)
        last_word = words.pop()

        ordinal = self.dict[last_word]
        w: Parse = self.parse(ordinal)

        tag = self.parse(first_word).tag
        w: Parse = w.inflect({tag.gender, tag.case})

        return " ".join(words + [w.word])

    def text_to_integer(self, text: str) -> int:
        integer = 0

        for word in re.findall("[а-я]+", text):
            # 1. Get normal form
            w: Parse = self.parse(word)
            word = w.normal_form

            # 2. Check word in dict
            numb = next((k for k, v in self.dict.items() if v == word), None)
            if numb is None:
                continue

            # 3. Check word is ordional
            if isinstance(numb, str):
                numb = next((k for k, v in self.dict.items() if v == numb), None)

            # 4. Check word is a thousand or a million
            if numb >= 1000:
                integer *= numb
                continue

            integer += numb

        return integer


def parse_number(value: Union[int, float, str]) -> (int, int, int):
    """Return integer and decimal parts and decimal part len."""
    if isinstance(value, str):
        value = float(value) if "." in value else int(value)

    if isinstance(value, float):
        # force round to 3 decimal len max
        i, d = str(round(value, 3)).split(".")
        return int(i), int(d), len(d)

    return value, 0, 0


def first(integer: int) -> bool:
    return (integer % 10 == 1) and (integer % 100 != 11)


def second(integer: int) -> bool:
    return (
        (integer % 10 >= 2)
        and (integer % 10 <= 4)
        and (integer % 100 < 10 or integer % 100 >= 20)
    )
