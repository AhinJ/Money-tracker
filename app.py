import streamlit as st
import pandas as pd
from pathlib import Path

# ==========================================
# PAGE SETTINGS
# ==========================================
st.set_page_config(
    page_title="Money Manager",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Save files in the same folder as this app.py
BASE_DIR = Path(__file__).resolve().parent
EXPENSE_FILE = BASE_DIR / "expenses.csv"
SAVINGS_FILE = BASE_DIR / "savings.csv"
GOALS_FILE = BASE_DIR / "goals.csv"


# ==========================================
# DATA FUNCTIONS
# ==========================================
def load_data(filename, columns):
    if filename.exists():
        try:
            df = pd.read_csv(filename)

            for column in columns:
                if column not in df.columns:
                    df[column] = None

            return df[columns]

        except Exception:
            return pd.DataFrame(columns=columns)

    return pd.DataFrame(columns=columns)


def save_data(df, filename):
    df.to_csv(filename, index=False)


def money(amount):
    return f"₩{amount:,.0f}"


# ==========================================
# LOAD DATA
# ==========================================
expense_columns = ["Date", "Category", "Amount", "Note"]
savings_columns = ["Date", "Goal", "Amount"]
goal_columns = ["Goal", "Target"]

expenses = load_data(EXPENSE_FILE, expense_columns)
savings = load_data(SAVINGS_FILE, savings_columns)
goals = load_data(GOALS_FILE, goal_columns)

expenses["Amount"] = pd.to_numeric(
    expenses["Amount"], errors="coerce"
).fillna(0)

savings["Amount"] = pd.to_numeric(
    savings["Amount"], errors="coerce"
).fillna(0)

goals["Target"] = pd.to_numeric(
    goals["Target"], errors="coerce"
).fillna(0)

# Remove invalid empty goal rows
goals = goals.dropna(subset=["Goal"])
goals = goals[goals["Goal"].astype(str).str.strip() != ""]


# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.title("💰 Money Manager")

page = st.sidebar.radio(
    "Navigate",
    ["My Money", "Progress", "Ranking", "Money Guide"]
)

st.sidebar.divider()

starting_money = st.sidebar.number_input(
    "Starting Money (₩)",
    min_value=0,
    value=50000,
    step=1000
)

st.sidebar.caption("Build better money habits, one step at a time!")


# ==========================================
# CALCULATE SAVINGS PROGRESS
# Used by BOTH Progress and Ranking
# ==========================================
def get_goal_summary():
    if goals.empty:
        return pd.DataFrame(
            columns=["Goal", "Target", "Saved", "Remaining", "Progress"]
        )

    summary = goals.copy()

    summary["Goal"] = summary["Goal"].astype(str)

    if savings.empty:
        summary["Saved"] = 0
    else:
        saved_by_goal = savings.groupby("Goal")["Amount"].sum()

        summary["Saved"] = summary["Goal"].map(
            saved_by_goal
        ).fillna(0)

    summary["Remaining"] = (
        summary["Target"] - summary["Saved"]
    ).clip(lower=0)

    summary["Progress"] = 0.0

    valid_targets = summary["Target"] > 0

    summary.loc[valid_targets, "Progress"] = (
        summary.loc[valid_targets, "Saved"]
        / summary.loc[valid_targets, "Target"]
        * 100
    )

    summary["Progress"] = summary["Progress"].clip(upper=100)

    return summary.sort_values(
        "Progress", ascending=False
    ).reset_index(drop=True)


# ==========================================
# PAGE 1: MY MONEY
# ==========================================
if page == "My Money":

    st.title("💰 My Money Summary")
    st.write("Record your expenses and savings in one place.")

    total_spent = float(expenses["Amount"].sum())
    total_saved = float(savings["Amount"].sum())
    remaining_money = starting_money - total_spent - total_saved

    col1, col2, col3 = st.columns(3)

    col1.metric("Starting Money", money(starting_money))
    col2.metric("Total Spent", money(total_spent))
    col3.metric("Money Remaining", money(remaining_money))

    st.divider()

    # --------------------------------------
    # ADD EXPENSE
    # --------------------------------------
    st.subheader("🛍️ Add an Expense")

    with st.form("expense_form", clear_on_submit=True):

        expense_date = st.date_input("Date")

        expense_category = st.selectbox(
            "Category",
            [
                "Food",
                "Snacks",
                "Shopping",
                "Transportation",
                "Entertainment",
                "School",
                "Clothing",
                "Other"
            ]
        )

        expense_amount = st.number_input(
            "Amount (₩)",
            min_value=0,
            step=500
        )

        expense_note = st.text_input("Note (optional)")

        expense_submit = st.form_submit_button("Add Expense")

    if expense_submit:

        if expense_amount <= 0:
            st.warning("Enter an amount greater than zero.")

        else:
            new_expense = pd.DataFrame([{
                "Date": str(expense_date),
                "Category": expense_category,
                "Amount": expense_amount,
                "Note": expense_note
            }])

            expenses = pd.concat(
                [expenses, new_expense],
                ignore_index=True
            )

            save_data(expenses, EXPENSE_FILE)

            st.success("Expense saved!")
            st.rerun()

    # --------------------------------------
    # SPENDING ANALYSIS
    # --------------------------------------
    st.divider()
    st.subheader("📊 Spending Analysis")

    if not expenses.empty and total_spent > 0:

        category_totals = expenses.groupby("Category")["Amount"].sum()

        category_percentages = (
            category_totals / category_totals.sum() * 100
        )

        st.bar_chart(category_totals)

        analysis = pd.DataFrame({
            "Total Spent (₩)": category_totals,
            "Spending (%)": category_percentages.round(1)
        })

        st.dataframe(analysis, use_container_width=True)

        top_category = category_totals.idxmax()
        top_percent = category_percentages[top_category]

        st.info(
            f"Your highest spending category is {top_category} "
            f"({top_percent:.1f}% of recorded spending)."
        )

        if top_percent >= 50:
            st.warning(
                "Consider setting a budget for this spending category."
            )

    else:
        st.info("Add an expense to see your spending analysis.")

    with st.expander("View Expense History"):

        if not expenses.empty:
            st.dataframe(
                expenses.sort_values("Date", ascending=False),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.write("No expenses recorded yet.")

    # --------------------------------------
    # CREATE A SAVINGS GOAL
    # --------------------------------------
    st.divider()
    st.subheader("🎯 Create a Savings Goal")

    st.write(
        "Create your goal and target amount once. "
        "Your Progress and Ranking pages will update automatically."
    )

    with st.form("create_goal_form", clear_on_submit=True):

        new_goal_name = st.text_input(
            "Goal Name",
            placeholder="e.g. Headphones"
        )

        new_goal_target = st.number_input(
            "Target Amount (₩)",
            min_value=1,
            value=30000,
            step=1000
        )

        create_goal_submit = st.form_submit_button("Create Goal")

    if create_goal_submit:

        if not new_goal_name.strip():
            st.warning("Please enter a goal name.")

        elif (
            goals["Goal"].astype(str).str.casefold()
            == new_goal_name.strip().casefold()
        ).any():
            st.warning(
                "This goal already exists. Select it below to add savings."
            )

        else:
            new_goal = pd.DataFrame([{
                "Goal": new_goal_name.strip(),
                "Target": new_goal_target
            }])

            goals = pd.concat(
                [goals, new_goal],
                ignore_index=True
            )

            save_data(goals, GOALS_FILE)

            st.success("Savings goal created!")
            st.rerun()

    # --------------------------------------
    # ADD SAVINGS TO AN EXISTING GOAL
    # --------------------------------------
    st.subheader("🐷 Add to My Savings")

    if not goals.empty:

        goal_names = goals["Goal"].astype(str).tolist()

        with st.form("add_savings_form", clear_on_submit=True):

            selected_goal = st.selectbox(
                "Choose an existing goal",
                goal_names
            )

            savings_date = st.date_input(
                "Savings Date",
                key="saving_date"
            )

            savings_amount = st.number_input(
                "Amount to Add (₩)",
                min_value=0,
                step=1000,
                key="saving_amount"
            )

            add_savings_submit = st.form_submit_button(
                "Add Savings"
            )

        if add_savings_submit:

            if savings_amount <= 0:
                st.warning("Enter an amount greater than zero.")

            else:
                new_saving = pd.DataFrame([{
                    "Date": str(savings_date),
                    "Goal": selected_goal,
                    "Amount": savings_amount
                }])

                savings = pd.concat(
                    [savings, new_saving],
                    ignore_index=True
                )

                save_data(savings, SAVINGS_FILE)

                st.success(
                    f"{money(savings_amount)} added to {selected_goal}!"
                )

                st.rerun()

        # Show current progress directly on My Money
        st.divider()
        st.subheader("📈 My Current Savings")

        current_summary = get_goal_summary()

        for _, row in current_summary.iterrows():

            st.write(
                f"**{row['Goal']}** — "
                f"{money(row['Saved'])} / {money(row['Target'])}"
            )

            st.progress(float(row["Progress"]) / 100)

            st.caption(
                f"Progress: {row['Progress']:.1f}%"
            )

    else:
        st.info("Create a savings goal above before adding savings.")


# ==========================================
# PAGE 2: PROGRESS
# ==========================================
elif page == "Progress":

    st.title("🎯 My Savings Progress")
    st.write("All progress is calculated from your saved records.")

    summary = get_goal_summary()

    if summary.empty:

        st.info(
            "You don't have a savings goal yet. "
            "Go to My Money to create one."
        )

    else:

        total_targets = float(summary["Target"].sum())
        total_goal_savings = float(summary["Saved"].sum())

        col1, col2, col3 = st.columns(3)

        col1.metric("Number of Goals", len(summary))
        col2.metric("Total Saved", money(total_goal_savings))
        col3.metric("Total Targets", money(total_targets))

        st.divider()

        for _, row in summary.iterrows():

            st.subheader(f"🎯 {row['Goal']}")

            col1, col2, col3 = st.columns(3)

            col1.metric("Saved", money(row["Saved"]))
            col2.metric("Target", money(row["Target"]))
            col3.metric("Remaining", money(row["Remaining"]))

            st.progress(float(row["Progress"]) / 100)

            st.write(
                f"**Goal Progress: {row['Progress']:.1f}%**"
            )

            if row["Progress"] >= 100:
                st.success("Goal completed! Congratulations!")
            else:
                st.caption(
                    f"You need {money(row['Remaining'])} more "
                    "to reach this goal."
                )

            st.divider()

        st.subheader("Compare Your Goals")

        chart_data = summary.set_index("Goal")[["Progress"]]

        st.bar_chart(chart_data)

        st.caption(
            "Progress is capped at 100% for display. "
            "Additional savings remain included in your saved total."
        )


# ==========================================
# PAGE 3: RANKING
# ==========================================
elif page == "Ranking":

    st.title("Ranking")

    st.write(
        "Your ranking is automatically generated from your savings goals."
    )

    summary = get_goal_summary()

    if summary.empty:

        st.info(
            "Create a savings goal and add savings on My Money "
            "to appear in this ranking."
        )

    else:

        ranking_table = summary[
            ["Goal", "Saved", "Target", "Progress"]
        ].copy()

        ranking_table = ranking_table.sort_values(
            ["Progress", "Saved"],
            ascending=[False, False]
        ).reset_index(drop=True)

        ranking_table.insert(
            0,
            "Rank",
            range(1, len(ranking_table) + 1)
        )

        ranking_table = ranking_table.rename(
            columns={
                "Saved": "Saved (₩)",
                "Target": "Target (₩)",
                "Progress": "Progress (%)"
            }
        )

        st.subheader("🥇Leaderboard")

        st.dataframe(
            ranking_table,
            use_container_width=True,
            hide_index=True
        )

        first_goal = ranking_table.iloc[0]

        st.success(
            f"Your top goal is **{first_goal['Goal']}** "
            f"with {first_goal['Progress']:.1f}% progress!"
        )

        st.caption(
            "This ranking compares your own goals. "
            "It is not a public ranking of different users."
        )


# ==========================================
# PAGE 4: MONEY GUIDE
# ==========================================
elif page == "Money Guide":

    st.title(" Money Guide")

    st.write(
        "Learn simple habits to manage your money wisely."
    )

    st.divider()

    st.subheader("1. The 50/30/20 Rule")

    col1, col2, col3 = st.columns(3)

    col1.metric("50%", "Needs")
    col2.metric("30%", "Wants")
    col3.metric("20%", "Savings")

    st.caption(
        "This is a general budgeting guideline. "
        "Adjust it to fit your circumstances."
    )

    st.divider()

    st.subheader("2. Five Smart Money Habits")

    st.markdown("""
    - **Track spending:** Record your purchases.
    - **Set a goal:** Decide what you want to save for.
    - **Save regularly:** Build a consistent savings habit.
    - **Think before buying:** Consider whether you need the item.
    - **Compare prices:** Check different options before purchasing.
    """)

    st.divider()

    st.subheader("3. Needs vs. Wants")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### ⭕ Needs")
        st.write(
            "Essential things such as transportation "
            "and necessary school supplies."
        )

    with col2:
        st.markdown("### ❌ Wants")
        st.write(
            "Extra things you would like, such as games, "
            "snacks, or accessories."
        )

    st.divider()

    st.subheader("4. Weekly Challenge")

    st.write("""
    1. Record your spending for one week.
    2. Find the category where you spend the most.
    3. Create a realistic savings goal.
    4. Check your progress at the end of the week.
    """)

    st.success(
        "Good money management is about making thoughtful choices, "
        "not about having the most money."
    )


# ==========================================
# FOOTER
# ==========================================
st.divider()

st.caption(
    "Money Manager | A student project for better financial habits."
)