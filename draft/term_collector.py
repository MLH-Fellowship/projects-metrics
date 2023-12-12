from datetime import datetime

start_date_1 = "2024-01-29"
end_date_1 = "2024-04-19"
start_date_2 = "2023-10-02"
end_date_2 = "2023-12-22"
start_date_3 = "2023-07-10"
end_date_3 = "2023-09-29"

now = datetime.now()

format = "%Y-%m-%d"


if datetime.strptime(start_date_3, format) < now and datetime.strptime(end_date_3, format) > now:
    print("This means the start date was in the past and the end date hasn't come yet")

def test():
    start_date_1 = "Hellos"
    print(start_date_1)
test()
print(start_date_1)