def total_price(order_ids, db):
    total = 0
    for order_id in order_ids:
        order = db.query(f"SELECT * FROM orders WHERE id = {order_id}")
        total += order["price"]
    return total


def find_pairs_with_sum(numbers, target):
    pairs = []
    for i in range(len(numbers)):
        for j in range(len(numbers)):
            if i != j and numbers[i] + numbers[j] == target:
                pairs.append((numbers[i], numbers[j]))
    return pairs


def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
