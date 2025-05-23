from decimal import Decimal
from wordcloud import WordCloud
from boto3.dynamodb.conditions import Key
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    jsonify,
    json,
    url_for,
    flash,
)
import boto3
import ast
import secrets
from boto3.dynamodb.conditions import Attr
from datetime import datetime


app = Flask(__name__)

app.config['SECRET_KEY'] = secrets.token_hex(16)

valid_credentials = [
    {"account": "1104523", "password": "4523"},
    {"account": "1104536", "password": "4536"},
    {"account": "1104549", "password": "4549"},
    {"account": "1104573", "password": "4573"},
    {"account": "admin", "password": "admin"},
]


# 載入 API 設定
def load_api_config():
    with open("static/data/api_config.json", "r") as f:
        return json.load(f)


# 讀取並設定 AWS 相關設定作為 Flask 應用程式的全局變數
api_config = load_api_config()
app.config["AWS_REGION"] = api_config["AWS_REGION"]
app.config["AWS_ACCESS_KEY_ID"] = api_config["AWS_ACCESS_KEY_ID"]
app.config["AWS_SECRET_ACCESS_KEY"] = api_config["AWS_SECRET_ACCESS_KEY"]

# 初始化 DynamoDB 資源
dynamodb = boto3.resource(
    "dynamodb",
    region_name=app.config["AWS_REGION"],
    aws_access_key_id=app.config["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=app.config["AWS_SECRET_ACCESS_KEY"],
)

table = dynamodb.Table("user")
table2 = dynamodb.Table("problems")
table3 = dynamodb.Table("rate")
table4 = dynamodb.Table("point")
table5 = dynamodb.Table("questions")
table6 = dynamodb.Table("report")


# 管理者首頁
@app.route("/", methods=["GET"])
def manager():
    return render_template("manager.html")


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    account = data.get("account")
    password = data.get("password")

    # 驗證帳號密碼
    for cred in valid_credentials:
        if cred["account"] == account and cred["password"] == password:
            return jsonify({"success": True, "message": "登入成功"})

    return jsonify({"success": False, "message": "登入失敗，請檢查您的帳號和密碼"})


#########################
#        點數管理       #
#######################
@app.route("/point", methods=["GET", "POST"])
def point():
    response3 = table3.scan()
    users = response3["Items"]

    response4 = table4.scan()
    points = response4["Items"]
    all_points = points.copy()  # 保留完整的點數列表

    if request.method == "POST":
        user_id = request.form.get("user_id")
        if user_id:
            # 使用者存在，找到對應的點數項目
            user_points = [point for point in points if point["使用者編號"] == user_id]
            if not user_points:
                flash("無此資料！")  # Add flash message
                return redirect(url_for("point"))
            # 按照交易編號排序
            sorted_points = sorted(user_points, key=lambda x: x["交易編號"])
            return render_template(
                "point.html", points=sorted_points, users=users, all_points=all_points, scroll_to='rectangle-content'
            )
        else:
            flash("請輸入使用者編號！")
            
        return redirect(url_for("point"))

    return render_template(
        "point.html", points=points, users=users, all_points=all_points, scroll_to='rectangle-content'
    )


@app.route("/update_total_points", methods=["POST"])
def update_total_points():
    userid = request.form.get("userid")  # 使用者編號
    transactionid = request.form.get("transactionid")  # 交易編號
    originalTotalPoints = int(request.form.get("originalTotalPoints"))  # 原始總點數
    newTotalPoints = int(
        request.form.get("newTotalPoints")
    )  # 把 newTotalPoints 轉換成整數
    print(f"New Total Points: {newTotalPoints}, type: {type(newTotalPoints)}")
    print(
        f"Original Total Points: {originalTotalPoints}, type: {type(originalTotalPoints)}"
    )
    # 如果交易編號為None，替換為'*'
    if not transactionid:
        transactionid = "*"

    print(userid)
    print(transactionid)

    def get_highest_transaction_id(userid):
        # 用使用者編號對使用者進行掃描
        response = table4.scan(FilterExpression=Key("使用者編號").eq(userid))
        # 從掃描的結果中找出最高的交易編號
        transaction_ids = [
            item["交易編號"]
            for item in response["Items"]
            if item["交易編號"].startswith("T")
        ]
        if transaction_ids:
            highest_id = max(transaction_ids)
        else:
            highest_id = "T000"

        return highest_id

    def increment_transaction_id(transaction_id):
        # 增加交易編號的數字(不包括"T"部分)
        try:
            number_part = int(transaction_id[1:])
            new_number_part = str(number_part + 1)

            # 保持交易編號始終有三位數
            while len(new_number_part) < 3:
                new_number_part = "0" + new_number_part
        except ValueError:
            new_number_part = "001"

        return "T" + new_number_part

    # 取得使用者的最高交易編號
    highest_id = get_highest_transaction_id(userid)

    # 計算新的交易編號
    new_id = increment_transaction_id(highest_id)

    # 在資料庫中建立新的資料
    table4.put_item(
        Item={
            "使用者編號": userid,
            "交易編號": new_id,
            "變動": int(int(newTotalPoints) - int(originalTotalPoints)),
            "日期": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),  # 加入當前日期
            "類型": "管理者修改",
        }
    )
    # 更新資料
    table4.update_item(
        Key={"使用者編號": userid, "交易編號": transactionid},
        UpdateExpression="SET #tp = :val, #type = :val2",
        ExpressionAttributeValues={":val": newTotalPoints, ":val2": "管理者修改"},
        ExpressionAttributeNames={"#tp": "總點數", "#type": "類型"},
    )

    # 響應返回到前端
    return jsonify({"message": "成功"}), 200


@app.route("/update_rate/<points>", methods=["POST"])
def update_rate(points):
    new_rate = request.form.get("rate")
    table3.update_item(
        Key={"點數": points},
        UpdateExpression="SET #r = :val1",
        ExpressionAttributeNames={"#r": "價格"},
        ExpressionAttributeValues={":val1": Decimal(str(new_rate))},
    )
    return redirect(url_for('point', success='true'))


#############################
#        分析報告管理       #
##########################
@app.route("/report", methods=["GET", "POST"])
def report():
    user_response = table.scan()
    user_items = user_response["Items"]
    user_names = {str(user["使用者編號"]): user["name"] for user in user_items}

    original_items = table6.scan()["Items"]
    items = original_items
    if request.method == "POST":
        user_name = request.form.get("user_name")
        user_id = [k for k, v in user_names.items() if v == user_name]
        if user_id:
            items = [
                item for item in original_items if str(item["使用者編號"]) == user_id[0]
            ]
        if not items or not user_id:
            flash("無此資料！")  # Add flash message
            return redirect(url_for("report"))

    for item in items:
        item["分析報告編號"] = str(item.get("分析報告編號", ""))
        item["人資題紀錄"] = item.get("人資題紀錄", [])
        item["日期"] = str(item.get("日期", ""))
        item["技術題紀錄"] = item.get("技術題紀錄", [])
        item["面試時長（秒）"] = str(item.get("面試時長（秒）", ""))
        item["概念題紀錄"] = item.get("概念題紀錄", [])

    return render_template("report.html", items=items, user_names=user_names)


@app.route("/delete_report", methods=["POST"])
def delete_report():
    try:
        # 尝试获取使用者編號和分析報告編號，并确保分析報告編號是整数
        userid = request.form["使用者編號"]
        print("使用者編號：", userid)
        reportid = request.form["分析報告編號"]
        print("分析報告編號：", reportid)
        # 删除 DynamoDB 表项
        response = table6.delete_item(
            Key={"使用者編號": str(userid), "分析報告編號": int(reportid)}
        )
        return redirect("/report")
    except Exception as e:
        print(e)
        return str(e), 500


#########################
#        題目管理       #
#######################
@app.route("/question", methods=["GET"])
def question():
    response = table5.scan()
    quest_items = response["Items"]

    # 分類題目
    HR_questions = [item for item in quest_items if item["關鍵字"] == "人資"]
    pro_questions = [item for item in quest_items if item["關鍵字"] == "概念"]
    code_questions = [item for item in quest_items if item["關鍵字"] == "技術"]

    return render_template(
        "question.html",
        HR_questions=HR_questions,
        pro_questions=pro_questions,
        code_questions=code_questions,
    )


@app.route("/delete_question/<string:keyword>/<string:question_id>", methods=["DELETE"])
def delete_question(keyword, question_id):
    table5.delete_item(Key={"關鍵字": keyword, "題目編號": question_id})
    return {}, 204


@app.route("/save_to_dynamodb/<string:keyword>/<string:question_id>", methods=["POST"])
def save_to_dynamodb(keyword, question_id):
    data = request.json
    editedContents = data.get("editedContents")
    tableType = data.get("tableType")

    # 檢查必要的參數是否存在
    if not editedContents:
        return jsonify({"error": "Missing required parameters"}), 400

    try:
        # 創建 DynamoDB 更新表達式
        update_expression = "SET "
        expression_attribute_names = {}
        expression_attribute_values = {}

        for key in editedContents:
            if isinstance(editedContents[key], str):
                editedContents[key] = editedContents[key].strip()

        # 根據 tableType 構建更新表達式和表達式屬性名稱/值
        if tableType == "HRbox":
            update_expression += "#content = :content"
            expression_attribute_names["#content"] = "題目內容"
            expression_attribute_values[":content"] = editedContents.get("題目內容", "")
        elif tableType == "box1":
            update_expression += "#content = :content, #category = :category"
            expression_attribute_names["#content"] = "題目內容"
            expression_attribute_names["#category"] = "類別"

            # 將類別字符串分割成列表
            category_string = editedContents.get("類別", "")
            category_list = [
                item.strip(" \"'\n")
                for item in category_string.strip(" \n{}[]").split(", ")
            ]

            expression_attribute_values[":content"] = editedContents.get("題目內容", "")
            expression_attribute_values[":category"] = category_list
        elif tableType == "box2":
            update_expression += "#tag = :tag, #difficulty = :difficulty, #content = :content, #category = :category"
            expression_attribute_names["#tag"] = "tag"
            expression_attribute_names["#difficulty"] = "難度"
            expression_attribute_names["#content"] = "題目內容"
            expression_attribute_names["#category"] = "類別"

            # 將類別字符串分割成列表
            category_string = editedContents.get("類別", "")
            category_list = [
                item.strip(" \"'\n")
                for item in category_string.strip(" \n{}[]").split(", ")
            ]
            tag_string = editedContents.get("tag", "")
            tag_list = [
                item.strip(" \"'\n") for item in tag_string.strip(" \n{}[]").split(", ")
            ]

            expression_attribute_values[":tag"] = tag_list
            expression_attribute_values[":difficulty"] = editedContents.get("難度", "")
            expression_attribute_values[":content"] = editedContents.get("題目內容", "")
            expression_attribute_values[":category"] = category_list
        else:
            return jsonify({"error": "Unknown table type"}), 400

        # 使用 DynamoDB resource 更新項目
        response = table5.update_item(
            Key={"關鍵字": keyword, "題目編號": question_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="UPDATED_NEW",
        )

        updated_item = response.get("Attributes")
        return (
            jsonify(
                {"message": "Item updated successfully", "updated_item": updated_item}
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


#########################
#        新增題目       #
#######################
@app.route("/addexam", methods=["GET"])
def addexam():
    return render_template("addexam.html")


@app.route("/json_data")
def json_data():
    #  讀取 JSON 文件的内容並返回
    try:
        with open(
            "./static/data/leetcode_problem_updated.json", "r", encoding="utf-8"
        ) as file:
            data = json.load(file)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "JSON 文件未找到"})
    except json.JSONDecodeError:
        return jsonify({"error": "JSON 解析失敗"})


@app.route("/get_max_question_number", methods=["GET"])
def get_max_question_number():
    try:
        response = table5.query(KeyConditionExpression=Key("關鍵字").eq("技術"))
        max_question_number = None
        for item in response["Items"]:
            try:
                question_number = int(item["題目編號"])
                if max_question_number is None or question_number > max_question_number:
                    max_question_number = question_number
            except ValueError:
                # 無法辨別為整數的情況，忽略該項目
                pass

        # 如果沒有找到整數題目編號，將 max_question_number 設置為 0
        if max_question_number is None:
            max_question_number = 0

        return jsonify({"maxQuestionNumber": max_question_number})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/submit", methods=["POST"])
def submit():
    try:
        user_selection = request.json
        table5.put_item(
            Item={
                "題目編號": str(user_selection["questionNumber"]),
                "關鍵字": "技術",
                "難度": user_selection["difficulty"],
                "題目內容": user_selection["questionContent"],
                "類別": user_selection["tools"] + user_selection["varieties"],
                "tag": user_selection.get("tags", []),
            }
        )
        return jsonify({"message": "User selection submitted successfully."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


###############################
#        使用者資料管理       #
############################
@app.route("/user", methods=["GET"])
def user():
    response = table.scan()
    items = response["Items"]
    return render_template("user.html", items=items)


@app.route("/delete_user/<string:user_id>", methods=["DELETE"])
def delete_user(user_id):
    table.delete_item(Key={"使用者編號": user_id})
    return {}, 204


#############################
#        問題回報管理       #
###########################
@app.route("/problem", methods=["GET"])
def problem():
    response = table2.scan()
    prob_items = response["Items"]

    # 分類問題
    analysis_problems = [item for item in prob_items if item["type"] == "分析報告問題"]
    point_problems = [item for item in prob_items if item["type"] == "點數問題"]
    question_problems = [item for item in prob_items if item["type"] == "題目問題"]

    return render_template(
        "problem.html",
        analysis_problems=analysis_problems,
        point_problems=point_problems,
        question_problems=question_problems,
    )


@app.route("/delete_problem/<string:usr_id>/<string:problem_id>", methods=["DELETE"])
def delete_problem(usr_id, problem_id):
    table2.delete_item(Key={"使用者編號": usr_id, "問題編號": problem_id})
    return {}, 204


if __name__ == "__main__":
    app.run(debug=True)
