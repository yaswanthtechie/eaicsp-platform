# Executive Dashboard
## Project Structure

frontend/
└── packages/
    └── dashboard/
        ├── public/
        ├── src/
        │   ├── assets/
        │   ├── components/
        │   │   ├── ForecastChart.tsx
        │   │   └── InventoryTable.tsx
        │   ├── mocks/
        │   │   ├── forecast.ts
        │   │   └── inventory.ts
        │   ├── types/
        │   │   └── forecast.ts
        │   ├── App.tsx
        │   ├── index.css
        │   ├── main.tsx
        │   └── tokens.ts
        ├── .gitignore
        ├── eslint.config.js
        ├── index.html
        ├── package.json
        ├── tsconfig.json
        ├── vite.config.ts
        └── README.md




## 1. I Built

* Built a **Sales Forecast Chart** using **Recharts** with mock sales data.
* Created an **Inventory Table** for the Executive Dashboard.
* Added a filter to display only the products with **low stock**.


## 2. How to Run the Project

1. Open the project in **VS Code**.
2. Open the terminal and run:

npm run dev

3. Open the local development URL displayed in the terminal (for example, `http://localhost:5173`) in Chrome or any other web browser.

## 3. If I Had Another Day

If I had another day, I would add more mock sales data to the forecast chart. The current chart uses only a small dataset to demonstrate the functionality, and adding more data would make the chart more meaningful and realistic.


## 4. Challenges Faced

While implementing the **Loading**, **Empty**, and **Error** states, I initially got stuck because I was not familiar with handling these states. After understanding the concept, I was able to implement them and now feel comfortable working with these states.

I also faced some difficulty while creating the sales forecast chart using Recharts. I referred to the Recharts documentation and the examples provided to understand how the chart components work. After practicing, I was able to build the chart successfully and gained confidence in using Recharts.
