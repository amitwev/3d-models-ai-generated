# חותמות לחימר / Clay stamps

כל חותמת מקבלת **מספר סידורי** (001, 002, …). המספר חרוט על הדופן הקדמית
(הארוכה) של החותמת, כך שתמיד אפשר לדעת איזו חותמת מודפסת מתאימה לאיזו שורה
בטבלה. אחרי שמנסים חותמת על חימר — עדכנו את עמודת "ציון / הערות".

Each stamp has a serial ID engraved (readable) on its front long wall. The text
on the stamp face is raised and **mirrored**, so the imprint in clay reads
correctly.

## קטלוג / Catalog

| ID | טקסט | פונט | מידות (רוחב×עומק×גובה) | עומק תבליט | קובץ | תצוגה | ציון / הערות |
|----|------|------|------------------------|-------------|------|-------|---------------|
| 001 | דינה | Alef Bold | 30×20×20 מ"מ | 2.0 מ"מ | [STL](stl/001_dina_alef-bold.stl) | [PNG](stl/001_dina_alef-bold_preview.png) | _טרם נבדק_ |
| 002 | דינה | Rubik Bold (מעוגל) | 30×20×20 מ"מ | 2.0 מ"מ | [STL](stl/002_dina_rubik-bold.stl) | [PNG](stl/002_dina_rubik-bold_preview.png) | _טרם נבדק_ |

הגובה הכולל (20 מ"מ) כולל את התבליט: בסיס 18 מ"מ + אותיות 2 מ"מ.

## הדפסה ב-Bambu Lab P2S

- **כיוון הדפסה:** כפי שהקובץ נטען — האותיות למעלה, הבסיס השטוח על המשטח.
  אין צורך בתמיכות.
- **חומר:** PLA או PETG.
- **גובה שכבה:** 0.12–0.16 מ"מ (פרופיל "Fine") לאותיות חדות.
- **מילוי:** 15–20% מספיק; 3 קירות.
- **Ironing** על המשטח העליון (אופציונלי) — נותן רקע חלק יותר בהטבעה.
- **טיפ לחימר:** לאבק את החותמת בקורנפלור / טלק או לשמן מעט לפני הלחיצה
  כדי שהחימר לא יידבק לאותיות.

## חותמת חדשה / Adding a stamp

1. הוסיפו רשומה ל-[`catalog.json`](catalog.json) עם `id` הבא בתור (לא לשנות
   מספרים קיימים — גם אם חותמת ישנה נמחקת).
2. הריצו:
   ```bash
   pip install -r stamps/requirements.txt
   python3 stamps/generate_stamps.py          # כל החותמות
   python3 stamps/generate_stamps.py 003      # רק חותמת 003
   ```
3. הוסיפו שורה לטבלה למעלה.

Fonts in [`fonts/`](fonts) are licensed under the SIL Open Font License
(see the `OFL-*.txt` files). `Rubik-Bold.ttf` is a static wght=700 instance of
the Rubik variable font.
