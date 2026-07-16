import os
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import (
    Flask, abort, flash, redirect, render_template,
    request, send_from_directory, session, url_for)
    
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from models import db, User, Message, Attachment


# مسیر اصلی پروژه

BASE_DIR = Path(__file__).resolve().parent

# پسوندهای مجاز برای فایل پیوست
ALLOWED_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg",
    "doc", "docx", "txt", "zip"
}


def allowed_file(filename):
    """بررسی مجاز بودن پسوند فایل"""
    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


def create_app(test_config=None):
    app = Flask(__name__)

    # تنظیمات اصلی برنامه
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY",
        "dev-secret-change-this"
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'messaging.db'}"
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = str(BASE_DIR / "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

    # در حالت تست، تنظیمات جدید جایگزین می‌شوند
    if test_config:
        app.config.update(test_config)

    # ساخت پوشه‌های موردنیاز
    Path(app.config["UPLOAD_FOLDER"]).mkdir(
        parents=True,
        exist_ok=True
    )
    (BASE_DIR / "instance").mkdir(
        parents=True,
        exist_ok=True
    )

    # اتصال دیتابیس به برنامه
    db.init_app(app)

    with app.app_context():
        db.create_all()

    # -------------------------------------------------
    # توابع کمکی
    # -------------------------------------------------

    def login_required(view_function):
        """جلوگیری از ورود کاربران مهمان به صفحات داخلی"""

        @wraps(view_function)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash(
                    "برای ادامه ابتدا وارد حساب خود شوید.",
                    "warning"
                )
                return redirect(url_for("login"))

            return view_function(*args, **kwargs)

        return wrapper

    def get_current_user():
        """دریافت کاربر واردشده"""
        user_id = session.get("user_id")

        if user_id is None:
            return None

        return db.session.get(User, user_id)

    @app.context_processor
    def add_current_user_to_templates():
        return {
            "current_user": get_current_user()
        }

    @app.template_filter("fa_datetime")
    def format_datetime(value):
        if value is None:
            return "—"

        return value.strftime("%Y/%m/%d - %H:%M")

    # -------------------------------------------------
    # صفحه اصلی
    # -------------------------------------------------

    @app.route("/")
    def index():
        if "user_id" in session:
            return redirect(url_for("dashboard"))

        return redirect(url_for("login"))

    # -------------------------------------------------
    # ثبت‌نام
    # -------------------------------------------------

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if "user_id" in session:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = request.form.get(
                "username",
                ""
            ).strip()

            email = request.form.get(
                "email",
                ""
            ).strip().lower()

            password = request.form.get(
                "password",
                ""
            )

            confirm_password = request.form.get(
                "confirm_password",
                ""
            )

            if len(username) < 3:
                flash(
                    "نام کاربری باید حداقل ۳ کاراکتر باشد.",
                    "danger"
                )

            elif "@" not in email or "." not in email:
                flash(
                    "ایمیل معتبر وارد کنید.",
                    "danger"
                )

            elif len(password) < 6:
                flash(
                    "رمز عبور باید حداقل ۶ کاراکتر باشد.",
                    "danger"
                )

            elif password != confirm_password:
                flash(
                    "تکرار رمز عبور یکسان نیست.",
                    "danger"
                )

            else:
                existing_user = User.query.filter(
                    or_(
                        User.username == username,
                        User.email == email
                    )
                ).first()

                if existing_user:
                    flash(
                        "این نام کاربری یا ایمیل قبلاً ثبت شده است.",
                        "danger"
                    )
                else:
                    new_user = User(
                        username=username,
                        email=email
                    )

                    new_user.set_password(password)

                    db.session.add(new_user)
                    db.session.commit()

                    flash(
                        "ثبت‌نام با موفقیت انجام شد. اکنون وارد شوید.",
                        "success"
                    )

                    return redirect(url_for("login"))

        return render_template(
            "register.html",
            page_title="ثبت‌نام"
        )

    # -------------------------------------------------
    # ورود
    # -------------------------------------------------

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if "user_id" in session:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            identity = request.form.get(
                "identity",
                ""
            ).strip()

            password = request.form.get(
                "password",
                ""
            )

            user = User.query.filter(
                or_(
                    User.username == identity,
                    User.email == identity.lower()
                )
            ).first()

            if user and user.check_password(password):
                session.clear()
                session["user_id"] = user.id

                flash(
                    f"خوش آمدید، {user.username}.",
                    "success"
                )

                return redirect(url_for("dashboard"))

            flash(
                "نام کاربری/ایمیل یا رمز عبور نادرست است.",
                "danger"
            )

        return render_template(
            "login.html",
            page_title="ورود"
        )

    # -------------------------------------------------
    # خروج
    # -------------------------------------------------

    @app.route("/logout")
    def logout():
        session.clear()

        flash(
            "با موفقیت از حساب خارج شدید.",
            "info"
        )

        return redirect(url_for("login"))

    # -------------------------------------------------
    # داشبورد
    # -------------------------------------------------

    @app.route("/dashboard")
    @login_required
    def dashboard():
        user_id = session["user_id"]

        inbox_count = Message.query.filter_by(
            receiver_id=user_id
        ).count()

        unread_count = Message.query.filter_by(
            receiver_id=user_id,
            is_read=False
        ).count()

        sent_count = Message.query.filter_by(
            sender_id=user_id
        ).count()

        recent_messages = (
            Message.query
            .filter_by(receiver_id=user_id)
            .order_by(Message.created_at.desc())
            .limit(5)
            .all()
        )

        return render_template(
            "dashboard.html",
            page_title="صفحه اصلی",
            inbox_count=inbox_count,
            unread_count=unread_count,
            sent_count=sent_count,
            recent_messages=recent_messages
        )

    # -------------------------------------------------
    # ارسال پیام
    # -------------------------------------------------

    @app.route("/compose", methods=["GET", "POST"])
    @login_required
    def compose():
        current_user_id = session["user_id"]

        users = (
            User.query
            .filter(User.id != current_user_id)
            .order_by(User.username)
            .all()
        )

        if request.method == "POST":
            receiver_id = request.form.get(
                "receiver_id",
                type=int
            )

            subject = request.form.get(
                "subject",
                ""
            ).strip()

            body = request.form.get(
                "body",
                ""
            ).strip()

            uploaded_file = request.files.get(
                "attachment"
            )

            receiver = db.session.get(
                User,
                receiver_id
            )

            if receiver is None or receiver.id == current_user_id:
                flash(
                    "گیرنده معتبر انتخاب کنید.",
                    "danger"
                )


            elif not subject or len(subject) > 150:
                flash(
                    "موضوع را وارد کنید؛ حداکثر ۱۵۰ کاراکتر.",
                    "danger"
                )

            elif not body:
                flash(
                    "متن پیام نمی‌تواند خالی باشد.",
                    "danger"
                )

            elif (
                uploaded_file
                and uploaded_file.filename
                and not allowed_file(uploaded_file.filename)
            ):
                flash(
                    "نوع فایل مجاز نیست.",
                    "danger"
                )

            else:
                new_message = Message(
                    sender_id=current_user_id,
                    receiver_id=receiver.id,
                    subject=subject,
                    body=body
                )

                db.session.add(new_message)
                db.session.flush()

                if uploaded_file and uploaded_file.filename:
                    original_name = secure_filename(
                        uploaded_file.filename
                    )

                    extension = original_name.rsplit(
                        ".",
                        1
                    )[1].lower()

                    stored_name = (
                        f"{uuid4().hex}.{extension}"
                    )

                    save_path = (
                        Path(app.config["UPLOAD_FOLDER"])
                        / stored_name
                    )

                    uploaded_file.save(save_path)

                    new_attachment = Attachment(
                        message_id=new_message.id,
                        original_name=original_name,
                        stored_name=stored_name
                    )

                    db.session.add(new_attachment)

                db.session.commit()

                flash(
                    "پیام با موفقیت ارسال شد.",
                    "success"
                )

                return redirect(url_for("sent"))

        return render_template(
            "compose.html",
            page_title="پیام جدید",
            users=users
        )

    # -------------------------------------------------
    # صندوق دریافت
    # -------------------------------------------------

    @app.route("/inbox")
    @login_required
    def inbox():
        messages = (
            Message.query
            .filter_by(receiver_id=session["user_id"])
            .order_by(Message.created_at.desc())
            .all()
        )

        return render_template(
            "inbox.html",
            page_title="صندوق دریافت",
            messages=messages
        )

    # -------------------------------------------------
    # پیام‌های ارسالی
    # -------------------------------------------------

    @app.route("/sent")
    @login_required
    def sent():
        messages = (
            Message.query
            .filter_by(sender_id=session["user_id"])
            .order_by(Message.created_at.desc())
            .all()
        )

        return render_template(
            "sent.html",
            page_title="پیام‌های ارسالی",
            messages=messages
        )

    # -------------------------------------------------
    # مشاهده جزئیات پیام
    # -------------------------------------------------

    @app.route("/message/<int:message_id>")
    @login_required
    def message_detail(message_id):
        message = db.session.get(
            Message,
            message_id
        )

        if message is None:
            abort(404)

        user_id = session["user_id"]

        has_access = user_id in {
            message.sender_id,
            message.receiver_id
        }

        if not has_access:
            abort(403)

        if (
            message.receiver_id == user_id
            and not message.is_read
        ):
            message.is_read = True
            db.session.commit()

        return render_template(
            "message_detail.html",
            page_title=message.subject,
            message=message
        )

    # -------------------------------------------------
    # دانلود فایل پیوست
    # -------------------------------------------------

    @app.route("/attachment/<int:attachment_id>")
    @login_required
    def download_attachment(attachment_id):
        attachment = db.session.get(
            Attachment,
            attachment_id
        )

        if attachment is None:
            abort(404)

        message = attachment.message
        user_id = session["user_id"]

        if user_id not in {
            message.sender_id,
            message.receiver_id
        }:
            abort(403)

        return send_from_directory(
            app.config["UPLOAD_FOLDER"],
            attachment.stored_name,
            as_attachment=True,
            download_name=attachment.original_name
        )

    # -------------------------------------------------
    # مدیریت خطاها
    # -------------------------------------------------

    @app.errorhandler(413)
    def file_too_large(error):
        flash(
            "حجم فایل نباید بیشتر از ۸ مگابایت باشد.",
            "danger"
        )

        return redirect(
            request.referrer or url_for("compose")
        )

    @app.errorhandler(403)
    def forbidden(error):
        return render_template(
            "error.html",
            page_title="دسترسی غیرمجاز",
            code=403,
            message="شما اجازه مشاهده این بخش را ندارید."
        ), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template(
            "error.html",
            page_title="صفحه پیدا نشد",
            code=404,
            message="صفحه یا پیام موردنظر پیدا نشد."
        ), 404

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
        
    )
