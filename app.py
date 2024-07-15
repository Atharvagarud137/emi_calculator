from flask import Flask, render_template, request, send_file, redirect, url_for
import plotly.graph_objs as go
from plotly.io import to_html
import math
from datetime import datetime
from io import BytesIO
import pdfkit
import urllib.parse

app = Flask(__name__)

def get_month_abbr(month):
    return datetime.strptime(str(month), "%m").strftime("%b")

def calculate_schedule(principal, rate, tenure_months):
    monthly_rate = rate / 12 / 100
    emi = principal * monthly_rate * math.pow(1 + monthly_rate, tenure_months) / (math.pow(1 + monthly_rate, tenure_months) - 1)
    schedule = []
    balance = principal
    loan_paid_to_date = 0.0

    current_year = datetime.now().year
    current_month = datetime.now().month

    for month in range(1, tenure_months + 1):
        interest_payment = balance * monthly_rate
        principal_payment = emi - interest_payment
        balance -= principal_payment
        loan_paid_to_date += principal_payment

        month_abbr = get_month_abbr(current_month)
        
        schedule.append({
            'year': current_year,
            'month': month_abbr,
            'principal': round(principal_payment, 2),
            'interest': round(interest_payment, 2),
            'total_payment': round(emi, 2),
            'balance': round(balance, 2),
            'loan_paid_to_date': round(loan_paid_to_date / principal * 100, 2)
        })

        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    return schedule

def generate_pdf(html_content):
    pdf_file = BytesIO()
    options = {
        'page-size': 'A4',
        'encoding': 'UTF-8'
    }
    pdf = pdfkit.from_string(html_content, False, options=options)
    pdf_file.write(pdf)
    pdf_file.seek(0)
    return pdf_file

@app.route('/', methods=['GET', 'POST'])
def emi_calculator():
    error_message = ""
    if request.method == 'POST':
        loan_amount = request.form.get('loan_amount')
        interest_rate = request.form.get('interest_rate')
        tenure_years = request.form.get('tenure_years')
        tenure_months = request.form.get('tenure_months')

        # Validations
        if not loan_amount or not interest_rate or not (tenure_years or tenure_months):
            error_message = "All fields are required."
            return render_template('index.html', error_message=error_message)
        try:
            loan_amount = float(loan_amount)
            interest_rate = float(interest_rate)
            if tenure_years:
                tenure = int(tenure_years) * 12
            else:
                tenure = int(tenure_months)
        except ValueError:
            error_message = "Fields should only contain numeric values."
            return render_template('index.html', error_message=error_message)

        if loan_amount < 100 or loan_amount > 1000000000:
            error_message = "Loan amount must be between 100 and 1,000,000,000."
            return render_template('index.html', error_message=error_message)
        if interest_rate < 2 or interest_rate > 20:
            error_message = "Interest rate must be between 2% and 20%."
            return render_template('index.html', error_message=error_message)
        
        # EMI Calculation using the formula
        monthly_interest_rate = interest_rate / 12 / 100
        emi = loan_amount * monthly_interest_rate * (1 + monthly_interest_rate) ** tenure / ((1 + monthly_interest_rate) ** tenure - 1)

        # Total Payments
        total_payment = emi * tenure
        total_interest = total_payment - loan_amount
        
        # Rounding to nearest whole number
        emi = round(emi)
        total_interest = round(total_interest)
        total_payment = round(total_payment)

        # Generate amortization schedule
        schedule = calculate_schedule(loan_amount, interest_rate, tenure)

        # Create Pie Chart
        labels = ['Total Interest', 'Principal Loan Amount']
        values = [total_interest, loan_amount]
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.3)])
        fig.update_layout(
            title_text='Break-up of Total Payment', title_x=0.5, 
            annotations=[dict(text='Break-up of Total Payment', x=0.5, y=1.1, font_size=15, showarrow=False)],
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.2,
                xanchor="center",
                x=0.5
            )
        )
        pie_chart = to_html(fig, full_html=False)

        return render_template('result.html', emi=emi, total_interest=total_interest, total_payment=total_payment,
                               pie_chart=pie_chart, schedule=schedule, loan_amount=loan_amount,
                               interest_rate=interest_rate, tenure_years=tenure_years, tenure_months=tenure_months)
    return render_template('index.html', error_message=error_message)

@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    loan_amount = float(request.form['loan_amount'])
    interest_rate = float(request.form['interest_rate'])
    tenure_years = request.form.get('tenure_years')
    tenure_months = request.form.get('tenure_months')
    tenure = int(tenure_years) * 12 if tenure_years else int(tenure_months)
    emi = float(request.form['emi'])
    total_interest = float(request.form['total_interest'])
    total_payment = float(request.form['total_payment'])

    # Create pie chart
    labels = ['Total Interest', 'Principal Loan Amount']
    values = [total_interest, loan_amount]
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.3)])
    pie_chart = to_html(fig, full_html=False)

    # Generate amortization schedule
    schedule = calculate_schedule(loan_amount, interest_rate, tenure)

    # Render HTML for PDF
    rendered_html = render_template('result.html', emi=emi, total_interest=total_interest,
                                    total_payment=total_payment, pie_chart=pie_chart,
                                    schedule=schedule, loan_amount=loan_amount,
                                    interest_rate=interest_rate, tenure_years=tenure_years,
                                    tenure_months=tenure_months)

    # Generate the PDF
    pdf = generate_pdf(rendered_html)
    if not pdf:
        return "Error generating PDF", 500
    return send_file(pdf, mimetype='application/pdf', as_attachment=True, download_name='emi_report.pdf')

@app.route('/share', methods=['POST'])
def share():
    loan_amount = request.form['loan_amount']
    interest_rate = request.form['interest_rate']
    tenure_years = request.form.get('tenure_years')
    tenure_months = request.form.get('tenure_months')

    params = {
        "loan_amount": loan_amount,
        "interest_rate": interest_rate,
        "tenure_years": tenure_years,
        "tenure_months": tenure_months
    }
    query_string = urllib.parse.urlencode(params)
    shareable_link = f"{request.url_root}share_link?{query_string}"
    return render_template('share.html', shareable_link=shareable_link)

@app.route('/share_link', methods=['GET'])
def share_link():
    loan_amount = request.args.get('loan_amount')
    interest_rate = request.args.get('interest_rate')
    tenure_years = request.args.get('tenure_years')
    tenure_months = request.args.get('tenure_months')

    if not loan_amount or not interest_rate or not (tenure_years or tenure_months):
        return redirect(url_for('emi_calculator'))

    try:
        loan_amount = float(loan_amount)
        interest_rate = float(interest_rate)
        if tenure_years:
            tenure = int(tenure_years) * 12
        else:
            tenure = int(tenure_months)
    except ValueError:
        return redirect(url_for('emi_calculator'))

    # Generate amortization schedule
    schedule = calculate_schedule(loan_amount, interest_rate, tenure)

    # Calculate EMI and Total Interest
    monthly_interest_rate = interest_rate / 12 / 100
    emi = loan_amount * monthly_interest_rate * (1 + monthly_interest_rate) ** tenure / ((1 + monthly_interest_rate) ** tenure - 1)
    total_payment = emi * tenure
    total_interest = total_payment - loan_amount

    emi = round(emi)
    total_interest = round(total_interest)
    total_payment = round(total_payment)

    # Create pie chart
    labels = ['Total Interest', 'Principal Loan Amount']
    values = [total_interest, loan_amount]
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.3)])
    pie_chart = to_html(fig, full_html=False)

    return render_template('result.html', emi=emi, total_interest=total_interest,
                           total_payment=total_payment, pie_chart=pie_chart,
                           schedule=schedule, loan_amount=loan_amount,
                           interest_rate=interest_rate, tenure_years=tenure_years,
                           tenure_months=tenure_months)

@app.route('/share.html')
def share_html():
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Shareable Link</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css">
        <style>
            .copy-btn {
                background: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 16px;
                cursor: pointer;
                margin-top: 10px;
            }

            .copy-btn:hover {
                background: #45a049;
            }

            .link-box {
                background: white;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                margin-top: 10px;
                word-wrap: break-word;
            }
        </style>
    </head>
    <body class="min-h-screen flex flex-col justify-center items-center bg-gray-100 text-gray-900">
        <div class="w-full max-w-md px-4 sm:px-0 mt-10 text-center">
            <h1 class="text-3xl font-bold mb-6">Your Shareable Link</h1>
            <div class="bg-white shadow-md rounded px-8 pt-6 pb-8 mb-4">
                <div class="link-box" id="shareable-link">{{ shareable_link }}</div>
                <button class="copy-btn" onclick="copyToClipboard()">Copy Link</button>
            </div>
        </div>

        <script>
            function copyToClipboard() {
                const copyText = document.getElementById('shareable-link').innerText;
                const tempInput = document.createElement('input');
                tempInput.value = copyText;
                document.body.appendChild(tempInput);
                tempInput.select();
                document.execCommand('copy');
                document.body.removeChild(tempInput);
                alert('Link copied to clipboard');
            }
        </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(debug=True)