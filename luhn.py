def luhn_check(card_number: str) -> bool:
    """
    Проверяет действительность номера с помощью алгоритма Луна.

    Аргументы:
    card_number (str): Строка, содержащая цифры номера, который нужно проверить.
                       Небуквенно-цифровые символы будут игнорироваться.

    Возвращает:
    bool: True, если номер действителен по алгоритму Луна, False в противном случае.
    """
    # 1. Удаляем все нецифровые символы и переворачиваем строку
    cleaned_number = ''.join(filter(str.isdigit, card_number))

    # Алгоритм Луна работает с перевернутым номером
    digits = [int(d) for d in cleaned_number[::-1]]

    total_sum = 0

    # 2. Итерируемся по цифрам, начиная со второй (индекс 1, 3, 5...)
    # Удваиваем каждую вторую цифру
    for i, digit in enumerate(digits):
        if i % 2 == 1:  # Каждая вторая цифра (начиная с предпоследней в оригинальном номере)
            doubled_digit = digit * 2
            if doubled_digit > 9:
                total_sum += (doubled_digit - 9)  # Или doubled_digit // 10 + doubled_digit % 10
            else:
                total_sum += doubled_digit
        else:  # Остальные цифры (контрольная цифра и каждая вторая от нее)
            total_sum += digit

    # 3. Проверяем, делится ли сумма на 10 без остатка
    return total_sum % 10 == 0