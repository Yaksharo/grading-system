# Grading System (prototype v0.1)

Imports UNP class list PDFs, records raw scores per grading component,
computes Midterm, Finals, and Semestral grades using the E-Class Record
formulation, and exports an Excel gradesheet with live formulas.

Developed by Yaksharo Solutions (Yaksharo a.k.a Ezer)

## Run it

```
pip install -r requirements.txt
python main.py
```

On Linux, install Tkinter once: `sudo apt install python3-tk`

## How to use

1. Home screen: "New Class from Class List PDF...", pick the portal's
   Class List PDF. Confirm the parsed students.
2. Class setup: check the school year, term, and subject info (pre-filled
   from the PDF), pick the subject type preset (Lecture with Laboratory
   20/25/25/30, Lecture 30/15/15/40, NSTP 30/10/20/40, or Custom), set
   how many score columns each component has.
3. Gradesheet: Midterm and Finals tabs. Type the Highest Possible Score
   in the yellow HPS row, then type scores. Initial Grade, Grade, and
   Remark compute live as you type. Scores above the HPS turn red.
4. Semestral tab: the 50/50 combination for the whole class.
5. Export gradesheet: choose Midterm only, Finals only, or Complete.
   The xlsx contains INPUT DATA, term sheets, and the semestral sheet
   with real formulas, so it shows the computation and recalculates in
   Excel.

Everything autosaves to `~/UNPGradingSystem/classes/` (one JSON file
per class). Copy that folder to move your data to another machine.

## Grading model (verified against the instructor's own gradesheets)

Per component: `PS = Total / HPS * 50 + 50`, `WS = PS x weight`.
Initial Grade = sum of the four WS. Grade via the transmutation table
(75 -> 3.00 ... 97-100 -> 1.00). PASSED at Initial >= 75.
Semestral Initial = 0.5 x Midterm + 0.5 x Finals, transmuted again.
