import smtplib
import ssl
from email.message import EmailMessage

from app.config import settings


def main():
    print("SMTP configuration check")
    print("Host:", settings.SMTP_HOST)
    print("Port:", settings.SMTP_PORT)
    print("Username configured:", bool(settings.SMTP_USERNAME.strip()))
    print("Password configured:", bool(settings.SMTP_PASSWORD.strip()))
    print("Sender configured:", bool(settings.SMTP_FROM_EMAIL.strip()))

    message = EmailMessage()
    message["Subject"] = "Felix Business Manager SMTP Test"
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = settings.SMTP_USERNAME
    message.set_content("This is a test of the application's email setup.")

    try:
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                context=ssl.create_default_context(),
                timeout=20,
            ) as server:
                server.login(
                    settings.SMTP_USERNAME,
                    settings.SMTP_PASSWORD,
                )
                server.send_message(message)
        else:
            with smtplib.SMTP(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=20,
            ) as server:
                server.ehlo()

                if settings.SMTP_USE_TLS:
                    server.starttls(
                        context=ssl.create_default_context()
                    )
                    server.ehlo()

                server.login(
                    settings.SMTP_USERNAME,
                    settings.SMTP_PASSWORD,
                )
                server.send_message(message)

        print("SMTP TEST PASSED: Test email sent.")

    except Exception as error:
        print("SMTP TEST FAILED")
        print("Error type:", type(error).__name__)
        print("Error details:", str(error))


if __name__ == "__main__":
    main()