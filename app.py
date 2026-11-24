import streamlit as st
import pandas as pd
from supabase import create_client


# ==========================================
# PAGE SETTINGS
# ==========================================
st.set_page_config(
    page_title="Money Manager",
    page_icon="💰",
    layout="wide"
)


# ==========================================
# SUPABASE CONFIG
# ==========================================
def get_public_config():
    return (
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )


def get_supabase():
    if "supabase_client" not in st.session_state:
        url, key = get_public_config()
        st.session_state["supabase_client"] = create_client(
            url,
            key
        )

    return st.session_state["supabase_client"]


supabase = get_supabase()


# ==========================================
# AUTHENTICATION
# ==========================================
user = None

try:
    user_response = supabase.auth.get_user()
    user = user_response.user
except Exception:
    user = None


# Connect Google login to Supabase
if st.user.is_logged_in and user is None:
    try:
        google_id_token = st.user.tokens.get("id")
        google_access_token = st.user.tokens.get("access")

        if not google_id_token:
            st.error("Google ID token is missing.")
            st.stop()

        if not google_access_token:
            st.error("Google access token is missing.")
            st.stop()

        credentials = {
            "provider": "google",
            "token": google_id_token,
            "access_token": google_access_token
        }

        response = supabase.auth.sign_in_with_id_token(
            credentials
        )

        user = response.user

    except Exception as error:
        st.error("Supabase login could not be completed.")
        st.write("Error type:", type(error).__name__)
        st.write("Error details:", str(error))
        st.stop()


# ==========================================
# LOGIN SCREEN
# ==========================================
if not st.user.is_logged_in:
    st.title("💰 Money Manager")

    st.write(
        "Track your money. Build better financial habits."
    )

    st.divider()
    st.subheader("Welcome!")

    st.write(
        "Sign in with Google to manage your money."
    )

    if st.button("Continue with Google", type="primary"):
        st.login()

    st.stop()


if user is None:
    st.error("Could not verify your Supabase login.")
    st.stop()


USER_ID = str(user.id)


# ==========================================
# NICKNAME SETUP
# ==========================================
try:
    profile_response = (
        supabase.table("profiles")
        .select("nickname")
        .eq("id", USER_ID)
        .maybe_single()
        .execute()
    )

    profile = profile_response.data

except Exception as error:
    st.error("Could not load your profile.")
    st.write(str(error))
    st.info(
        "Check that you have run the profiles SQL "
        "in Supabase SQL Editor."
    )
    st.stop()


# First-time users must create a nickname
if not profile:
    st.title("💰 Welcome to Money Manager!")

    st.subheader("Create Your Nickname")

    st.write(
        "Choose a nickname that other users can see "
        "on the Ranking page."
    )

    with st.form("nickname_form"):
        new_nickname = st.text_input(
            "Nickname",
            max_chars=20,
            placeholder="Enter a nickname"
        )

        nickname_submit = st.form_submit_button(
            "Save Nickname",
            type="primary"
        )

    if nickname_submit:
        nickname = new_nickname.strip()

        if len(nickname) < 2:
            st.warning(
                "Your nickname must be at least 2 characters."
            )

        elif len(nickname) > 20:
            st.warning(
                "Your nickname must be 20 characters or less."
            )

        else:
            try:
                supabase.table("profiles").insert({
                    "id": USER_ID,
                    "nickname": nickname
                }).execute()

                st.success("Nickname saved!")
                st.rerun()

            except Exception:
                st.error(
                    "This nickname may already be taken. "
                    "Please try another one."
                )

    st.stop()


NICKNAME = profile["nickname"]


# ==========================================
# DATA FUNCTIONS
# ==========================================
def load_table(table, columns):
    try:
        query = supabase.table(table).select("*")

        if "Date" in columns:
            query = query.order("Date", desc=True)

        response = query.execute()
        data = response.data or []

        if not data:
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(data)

        for column in columns:
            if column not in df.columns:
                df[column] = None

        return df[columns]

    except Exception as error:
        st.error(f"Could not load {table}: {error}")
        return pd.DataFrame(columns=columns)


def add_record(table, record):
    record["user_id"] = USER_ID

    supabase.table(table).insert(
        record
    ).execute()


def money(amount):
    return f"₩{amount:,.0f}"


# ==========================================
# LOAD USER DATA
# ==========================================
expense_columns = [
    "Date",
    "Category",
    "Amount",
    "Note"
]

savings_columns = [
    "Date",
    "Goal",
    "Amount"
]

goal_columns = [
    "Goal",
    "Target"
]


expenses = load_table(
    "expenses",
    expense_columns
)

savings = load_table(
    "savings",
    savings_columns
)

goals = load_table(
    "goals",
    goal_columns
)


# Convert numbers
expenses["Amount"] = pd.to_numeric(
    expenses["Amount"],
    errors="coerce"
).fillna(0)

savings["Amount"] = pd.to_numeric(
    savings["Amount"],
    errors="coerce"
).fillna(0)

goals["Target"] = pd.to_numeric(
    goals["Target"],
    errors="coerce"
).fillna(0)


# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.title("💰 Money Manager")

page = st.sidebar.radio(
    "Navigate",
    [
        "My Money",
        "Progress",
        "Ranking",
        "Money Guide"
    ]
)

st.sidebar.divider()

starting_money = st.sidebar.number_input(
    "Starting Money (₩)",
    min_value=0,
    value=50000,
    step=1000
)

st.sidebar.caption(
    "Build better money habits, one step at a time!"
)

st.sidebar.divider()

st.sidebar.write(
    f"Signed in as **{NICKNAME}**"
)

if st.sidebar.button("Log Out"):
    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    st.session_state.pop(
        "supabase_client",
        None
    )

    st.logout()


# ==========================================
# SAVINGS SUMMARY
# ==========================================
def get_goal_summary():

    if goals.empty:
        return pd.DataFrame(
            columns=[
                "Goal",
                "Target",
                "Saved",
                "Remaining",
                "Progress"
            ]
        )

    summary = goals.copy()

    if savings.empty:
        summary["Saved"] = 0

    else:
        saved_by_goal = savings.groupby(
            "Goal"
        )["Amount"].sum()

        summary["Saved"] = summary["Goal"].map(
            saved_by_goal
        ).fillna(0)

    summary["Remaining"] = (
        summary["Target"] - summary["Saved"]
    ).clip(lower=0)

    summary["Progress"] = 0.0

    valid = summary["Target"] > 0

    summary.loc[valid, "Progress"] = (
        summary.loc[valid, "Saved"]
        / summary.loc[valid, "Target"] * 100
    )

    summary["Progress"] = summary[
        "Progress"
    ].clip(upper=100)

    return summary.sort_values(
        "Progress",
        ascending=False
    ).reset_index(drop=True)


# ==========================================
# PAGE 1: MY MONEY
# ==========================================
if page == "My Money":

    st.title("💰 My Money Summary")

    st.write(
        "Record your expenses and savings in one place."
    )

    total_spent = float(
        expenses["Amount"].sum()
    )

    total_saved = float(
        savings["Amount"].sum()
    )

    remaining_money = (
        starting_money - total_spent - total_saved
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Starting Money",
        money(starting_money)
    )

    col2.metric(
        "Total Spent",
        money(total_spent)
    )

    col3.metric(
        "Money Remaining",
        money(remaining_money)
    )

    # ADD EXPENSE
    st.divider()
    st.subheader("🛍️ Add an Expense")

    with st.form(
        "expense_form",
        clear_on_submit=True
    ):

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

        expense_note = st.text_input(
            "Note (optional)"
        )

        expense_submit = st.form_submit_button(
            "Add Expense"
        )

    if expense_submit:

        if expense_amount <= 0:
            st.warning(
                "Enter an amount greater than zero."
            )

        else:
            try:
                add_record(
                    "expenses",
                    {
                        "Date": str(expense_date),
                        "Category": expense_category,
                        "Amount": expense_amount,
                        "Note": expense_note
                    }
                )

                st.success("Expense saved!")
                st.rerun()

            except Exception as error:
                st.error(
                    f"Could not save expense: {error}"
                )


    # SPENDING ANALYSIS
    st.divider()
    st.subheader("📊 Spending Analysis")

    if not expenses.empty and total_spent > 0:

        category_totals = expenses.groupby(
            "Category"
        )["Amount"].sum()

        category_percentages = (
            category_totals
            / category_totals.sum()
            * 100
        )

        st.bar_chart(category_totals)

        analysis = pd.DataFrame({
            "Total Spent (₩)": category_totals,
            "Spending (%)": category_percentages.round(1)
        })

        st.dataframe(
            analysis,
            use_container_width=True
        )

        top_category = category_totals.idxmax()

        top_percent = category_percentages[
            top_category
        ]

        st.info(
            f"Your highest spending category is "
            f"{top_category} ({top_percent:.1f}% "
            "of recorded spending)."
        )

        if top_percent >= 50:
            st.warning(
                "Consider setting a budget for this spending category."
            )

    else:
        st.info(
            "Add an expense to see your spending analysis."
        )


    # EXPENSE HISTORY
    with st.expander("View Expense History"):

        if not expenses.empty:
            st.dataframe(
                expenses.sort_values(
                    "Date",
                    ascending=False
                ),
                use_container_width=True,
                hide_index=True
            )

        else:
            st.write("No expenses recorded yet.")


    # CREATE GOAL
    st.divider()
    st.subheader("🎯 Create a Savings Goal")

    with st.form(
        "create_goal_form",
        clear_on_submit=True
    ):

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

        create_goal_submit = st.form_submit_button(
            "Create Goal"
        )

    if create_goal_submit:

        if not new_goal_name.strip():
            st.warning(
                "Please enter a goal name."
            )

        elif (
            goals["Goal"].astype(str).str.casefold()
            == new_goal_name.strip().casefold()
        ).any():

            st.warning(
                "This goal already exists."
            )

        else:
            try:
                add_record(
                    "goals",
                    {
                        "Goal": new_goal_name.strip(),
                        "Target": new_goal_target
                    }
                )

                st.success("Savings goal created!")
                st.rerun()

            except Exception as error:
                st.error(
                    f"Could not create goal: {error}"
                )


    # ADD SAVINGS
    st.subheader("🐷 Add to My Savings")

    if not goals.empty:

        goal_names = goals["Goal"].astype(
            str
        ).tolist()

        with st.form(
            "add_savings_form",
            clear_on_submit=True
        ):

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
                st.warning(
                    "Enter an amount greater than zero."
                )

            else:
                try:
                    add_record(
                        "savings",
                        {
                            "Date": str(savings_date),
                            "Goal": selected_goal,
                            "Amount": savings_amount
                        }
                    )

                    st.success(
                        f"{money(savings_amount)} "
                        f"added to {selected_goal}!"
                    )

                    st.rerun()

                except Exception as error:
                    st.error(
                        f"Could not save savings: {error}"
                    )

        st.divider()
        st.subheader("📈 My Current Savings")

        current_summary = get_goal_summary()

        for _, row in current_summary.iterrows():

            st.write(
                f"**{row['Goal']}** — "
                f"{money(row['Saved'])} / "
                f"{money(row['Target'])}"
            )

            st.progress(
                float(row["Progress"]) / 100
            )

            st.caption(
                f"Progress: {row['Progress']:.1f}%"
            )

    else:
        st.info(
            "Create a savings goal above before adding savings."
        )


# ==========================================
# PAGE 2: PROGRESS
# ==========================================
elif page == "Progress":

    st.title("🎯 My Savings Progress")

    st.write(
        "All progress is calculated from your saved records."
    )

    summary = get_goal_summary()

    if summary.empty:
        st.info(
            "You don't have a savings goal yet. "
            "Go to My Money to create one."
        )

    else:

        total_targets = float(
            summary["Target"].sum()
        )

        total_goal_savings = float(
            summary["Saved"].sum()
        )

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Number of Goals",
            len(summary)
        )

        col2.metric(
            "Total Saved",
            money(total_goal_savings)
        )

        col3.metric(
            "Total Targets",
            money(total_targets)
        )

        st.divider()

        for _, row in summary.iterrows():

            st.subheader(
                f"🎯 {row['Goal']}"
            )

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "Saved",
                money(row["Saved"])
            )

            col2.metric(
                "Target",
                money(row["Target"])
            )

            col3.metric(
                "Remaining",
                money(row["Remaining"])
            )

            st.progress(
                float(row["Progress"]) / 100
            )

            st.write(
                f"**Goal Progress: {row['Progress']:.1f}%**"
            )

            if row["Progress"] >= 100:
                st.success(
                    "Goal completed! Congratulations!"
                )

            else:
                st.caption(
                    f"You need {money(row['Remaining'])} "
                    "more to reach this goal."
                )

            st.divider()

        st.subheader("Compare Your Goals")

        chart_data = summary.set_index(
            "Goal"
        )[["Progress"]]

        st.bar_chart(chart_data)

        st.caption(
            "Progress is capped at 100% for display. "
            "Additional savings remain included in your saved total."
        )


# ==========================================
# PAGE 3: RANKING
# ==========================================
elif page == "Ranking":

    st.title("🏆 Savings Ranking")

    st.write(
        "Compare your savings progress with other users "
        "who have goals in the same target range."
    )

    try:
        ranking_response = supabase.rpc(
            "get_grouped_leaderboard"
        ).execute()

        ranking_data = ranking_response.data or []

    except Exception as error:
        ranking_data = None

        st.error(
            "Could not load the public ranking."
        )

        st.write(str(error))

        st.info(
            "Please check that the leaderboard SQL function "
            "has been created in Supabase."
        )


    if ranking_data is not None:

        if not ranking_data:

            st.info(
                "There are no active goals in the ranking yet. "
                "Create a goal and add savings to participate."
            )

        else:

            ranking_df = pd.DataFrame(ranking_data)

            ranking_df["bucket_min"] = pd.to_numeric(
                ranking_df["bucket_min"],
                errors="coerce"
            )

            ranking_df["bucket_max"] = pd.to_numeric(
                ranking_df["bucket_max"],
                errors="coerce"
            )

            ranking_df["target"] = pd.to_numeric(
                ranking_df["target"],
                errors="coerce"
            )

            ranking_df["progress"] = pd.to_numeric(
                ranking_df["progress"],
                errors="coerce"
            )

            ranking_df["rank"] = pd.to_numeric(
                ranking_df["rank"],
                errors="coerce"
            )

            ranking_df = ranking_df.sort_values(
                ["bucket_min", "rank"]
            )

            st.caption(
                "Each user appears only once in each target range. "
                "If a user has multiple goals in the same range, "
                "only their highest-progress goal is counted."
            )

            st.caption(
                "Completed goals (100% progress) are excluded."
            )

            st.divider()

            for (bucket_min, bucket_max), group in (
                ranking_df.groupby(
                    ["bucket_min", "bucket_max"],
                    sort=True
                )
            ):

                st.subheader(
                    f"🎯 {money(bucket_min)} – {money(bucket_max)}"
                )

                display_df = group[
                    [
                        "rank",
                        "nickname",
                        "goal_name",
                        "target",
                        "progress"
                    ]
                ].copy()

                display_df = display_df.rename(
                    columns={
                        "rank": "Rank",
                        "nickname": "Nickname",
                        "goal_name": "Goal",
                        "target": "Target (₩)",
                        "progress": "Progress (%)"
                    }
                )

                display_df["Target (₩)"] = (
                    display_df["Target (₩)"].apply(money)
                )

                display_df["Progress (%)"] = (
                    display_df["Progress (%)"].map(
                        lambda value: f"{value:.1f}%"
                    )
                )

                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True
                )

                st.divider()


# ==========================================
# PAGE 4: MONEY GUIDE
# ==========================================
elif page == "Money Guide":

    st.title("Money Guide")

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
