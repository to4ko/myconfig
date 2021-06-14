from pymorphy2 import MorphAnalyzer
from pymorphy2.analyzer import Parse

ONES = (None, 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь',
        'восемь', 'девять', 'десять', 'одиннадцать', 'двенадцать',
        'тринадцать', 'четырнадцать', 'пятнадцать', 'шестнадцать',
        'семнадцать', 'восемнадцать', 'девятнадцать')
TWENTIES = (None, None, 'двадцать', 'тридцать', 'сорок', 'пятьдесят',
            'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто')
HUNDREDS = (None, 'сто', 'двести', 'триста', 'четыреста', 'пятьсот',
            'шестьсот', 'семьсот', 'восемьсот', 'девятьсот')
THOUSANDS = (None, 'тысяча', 'миллион', 'миллиард', 'триллион')

MORPH = MorphAnalyzer()


def number_to_words(number: int, text: str = None):
    if number < 0:
        return ['минус'] + number_to_words(-number, text)

    if number == 0:
        return ['ноль']

    # граммемы последней цифры
    if text:
        word = text.rsplit(' ', 1)[-1]
        w: Parse = MORPH.parse(word)[0]
        tag = w.tag
    else:
        tag = None

    d3 = 0
    d2 = 0
    words = []

    k = len(str(number)) - 1
    for d in str(number):
        d = int(d)

        if k % 3 == 2:
            if d:
                words.append(HUNDREDS[d])
            d3 = d

        elif k % 3 == 1:
            if d > 1:
                words.append(TWENTIES[d])
            d2 = d

        else:
            # десять, одинадцать, двенадцать...
            if d2 == 1:
                d += 10

            if d:
                # тысячи женского рода (только для 1 и 2)
                if k == 3 and d <= 2:
                    w: Parse = MORPH.parse(ONES[d])[0]
                    w: Parse = w.inflect({'femn'})
                    words.append(w.word)

                # граммемы последней цифры (только для 1 и 2)
                elif k == 0 and d <= 2 and tag:
                    w: Parse = MORPH.parse(ONES[d])[0]
                    w: Parse = w.inflect({tag.gender, tag.case})
                    words.append(w.word)

                else:
                    words.append(ONES[d])

            # тысяч, миллион, миллиард...
            if k > 2 and (d3 or d2 or d):
                w2: Parse = MORPH.parse(THOUSANDS[int(k / 3)])[0]
                w2: Parse = w2.make_agree_with_number(d)
                words.append(w2.word)

        k -= 1

    return words


def words_with_number(number: int, text: str):
    number = abs(number)
    words = []
    for word in text.split(' '):
        w: Parse = MORPH.parse(word)[0]
        w: Parse = w.make_agree_with_number(number)
        words.append(w.word)
    return words


def numword(number, text: str = None, as_text: bool = True):
    number = int(float(number))

    if as_text is True:
        words = number_to_words(number, text)
    elif as_text is False:
        words = [str(number)]
    else:
        words = []

    if text:
        words += words_with_number(number, text)

    return ' '.join(words)
