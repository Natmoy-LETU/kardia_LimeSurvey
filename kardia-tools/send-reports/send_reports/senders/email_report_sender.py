import email
import email.policy
import mimetypes
import os
import smtplib
from datetime import datetime
from send_reports.models import ScheduledReport, SendingInfo, SentStatus
from send_reports.senders.sender import ReportSender
from typing import Dict, List

class EmailReportSender(ReportSender):

    def __init__(self, smtp_params: Dict[str, str]):
        self.smtp_params = smtp_params

    def _get_replaceable_params(self, scheduled_report: ScheduledReport):
        replaceable_params = {
            param_name: param.value 
            for param_name, param in scheduled_report.params.items() 
            if param.pass_to_template
        }
        replaceable_params["name"] = scheduled_report.recipient_name
        replaceable_params["email"] = scheduled_report.recipient_contact_info
        return replaceable_params

    # contact_info is assumed to be a string email
    def send_report(self, report_path, scheduled_report):
        if scheduled_report.recipient_contact_info is None:
            return SendingInfo(
                SentStatus.INVALID_EMAIL_ERROR,
                None,
                error_message='No email address')

        # Gather replaceable parameters and replace them in the template
        replaceable_params = self._get_replaceable_params(scheduled_report)
        email_text = scheduled_report.template
        for param_name, param_value in replaceable_params.items():
            email_text = email_text.replace(f'[:{param_name}]', param_value)

        # Create an email message and attach the report file
        msg = email.message_from_string(email_text, policy=email.policy.EmailPolicy())
        # These headers necessary for add_attachment to notice there's an existing email body and not just overwrite it
        msg["Content-Type"] = 'text/plain; charset="utf-8"'
        msg["Content-Transfer-Encoding"] = "7bit"
        (_, filename) = os.path.split(report_path.get_full_path())
        # Try to guess the report file's MIME type, but default to PDF
        report_type = mimetypes.guess_type(filename)[0] or "application/pdf"
        maintype, subtype = report_type.split("/")
        with open(report_path.get_full_path(), 'rb') as fp:
            msg.add_attachment(fp.read(), maintype=maintype, subtype=subtype, filename=filename)

        try:
            smtp = smtplib.SMTP(**self.smtp_params)
            smtp.send_message(msg)
            smtp.quit()
        except smtplib.SMTPResponseException as se:
            return SendingInfo(
                SentStatus.FAILURE_OTHER_ERROR,
                None,
                error_message=f'{se.smtp_code} {se.smtp_error}')

        return SendingInfo(SentStatus.SENT, datetime.now())