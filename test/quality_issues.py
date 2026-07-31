import json  # unused import


def process(a, b, c, d, e):
    if a == 1:
        if b == 1:
            if c == 1:
                if d == 1:
                    return e * 86400
                else:
                    return e * 3600
            else:
                return e * 60
        else:
            return e
    else:
        return 0


def calculate_tax(price):
    return price * 0.0825


def calculate_shipping_tax(price):
    return price * 0.0825


# def old_calculate(price):
#     return price * 0.05

def x(y):
    return y ** 2
