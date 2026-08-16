# DAX Measures

Assumptions:

- Detail table name: `Complaints`
- Run table name: `Ingestion Runs`
- Rejection table name: `Rejected Records`
- Date table name: `Date`

## Date table

```DAX
Date =
VAR MinDate = MINX(Complaints, Complaints[date_received])
VAR MaxDate = MAXX(Complaints, Complaints[date_received])
RETURN
ADDCOLUMNS(
    CALENDAR(MinDate, MaxDate),
    "Year", YEAR([Date]),
    "Month Number", MONTH([Date]),
    "Month", FORMAT([Date], "MMM"),
    "Year Month", FORMAT([Date], "YYYY-MM"),
    "Year Month Sort", YEAR([Date]) * 100 + MONTH([Date]),
    "Quarter", "Q" & FORMAT([Date], "Q")
)
```

Sort `Date[Year Month]` by `Date[Year Month Sort]`. Mark the table as a date table using `Date[Date]`.

## Core measures

```DAX
Complaint Count =
COUNTROWS(Complaints)
```

```DAX
Timely Complaint Count =
CALCULATE(
    [Complaint Count],
    Complaints[timely_response] = TRUE()
)
```

```DAX
Timely Response Rate =
DIVIDE([Timely Complaint Count], [Complaint Count])
```

```DAX
Disputed Amount =
SUM(Complaints[amount_disputed])
```

```DAX
Average Disputed Amount =
AVERAGE(Complaints[amount_disputed])
```

```DAX
Company Count =
DISTINCTCOUNT(Complaints[company])
```

```DAX
Open Complaint Count =
CALCULATE(
    [Complaint Count],
    Complaints[status] = "In progress"
)
```

```DAX
Open Complaint Rate =
DIVIDE([Open Complaint Count], [Complaint Count])
```

## Time measures

```DAX
Complaints Previous Month =
CALCULATE(
    [Complaint Count],
    DATEADD('Date'[Date], -1, MONTH)
)
```

```DAX
Complaint Month-over-Month Change =
[Complaint Count] - [Complaints Previous Month]
```

```DAX
Complaint Month-over-Month Percent =
DIVIDE(
    [Complaint Month-over-Month Change],
    [Complaints Previous Month]
)
```

```DAX
Complaints Year to Date =
TOTALYTD([Complaint Count], 'Date'[Date])
```

## Operational measures

```DAX
Rows Read =
SUM('Ingestion Runs'[rows_read])
```

```DAX
Rows Valid =
SUM('Ingestion Runs'[rows_valid])
```

```DAX
Rows Rejected =
SUM('Ingestion Runs'[rows_rejected])
```

```DAX
Acceptance Rate =
DIVIDE([Rows Valid], [Rows Read])
```

```DAX
Rejection Rate =
DIVIDE([Rows Rejected], [Rows Read])
```

```DAX
Vectors Upserted =
SUM('Ingestion Runs'[vectors_upserted])
```

```DAX
Failed Run Count =
CALCULATE(
    COUNTROWS('Ingestion Runs'),
    'Ingestion Runs'[status] = "FAILED"
)
```

## Display helpers

```DAX
Last Data Refresh =
"Report refreshed " & FORMAT(NOW(), "MMM d, yyyy h:mm AM/PM")
```

```DAX
Selected Scope =
VAR ProductSelection = SELECTEDVALUE(Complaints[product], "All products")
VAR StateSelection = SELECTEDVALUE(Complaints[state], "All states")
RETURN ProductSelection & " | " & StateSelection
```

## Formatting

- Timely Response Rate, Open Complaint Rate, Acceptance Rate, Rejection Rate, and month-over-month percent: Percentage, 1 decimal place
- Disputed Amount and Average Disputed Amount: Currency
- Counts: Whole number with thousands separator
