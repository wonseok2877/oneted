import boto3
import uuid
import json

from json.decoder       import JSONDecodeError
from django.views       import View
from django.http        import JsonResponse
from django.utils       import timezone

from resumes.models     import Resume, Apply, ResumeApply
from my_settings        import AWS_S3_ACCESS_KEY_ID, AWS_S3_SECRET_ACCESS_KEY, BUCKET, AWS_S3_URL
from utils              import authorization

class ResumesView(View):
    @authorization
    def get(self, request):
        resumes = Resume.objects.filter(user=request.user)
        result = [{
                "id"      : resume.id,
                "title"   : resume.title,
                "isDone"  : resume.is_done,
                "isFile"  : resume.is_file,
                "fileUrl" : resume.file_url
            }for resume in resumes]

        return JsonResponse({"message" : "SUCCESS", "result" : result}, status=200)
        
    @authorization        
    def post(self, request):
        try:
            data = json.loads(request.body)
            Resume.objects.create(
                user    = request.user,
                is_done = data["isDone"],
                title   = data["title"],
                content = {
                "description" : data["description"],
                "career"      : data["career"],
                "education"   : data["education"],
                "skill"       : data["skill"],
                })
            return JsonResponse({"message" : "SUCCESS"}, status=200)

        except KeyError:
            return JsonResponse({"message" : "KEY_ERROR"}, status=400)

        except JSONDecodeError:
            return JsonResponse({"message" : "JSON_DECODE_ERROR"}, status=400)

class ResumeView(View):

    @authorization
    def get(self, request, resume_id):
        if not Resume.objects.filter(id=resume_id, user=request.user).exists():
            return JsonResponse({"message" : "RESUME_NOT_FOUND"}, status=401)

        resume = Resume.objects.get(id=resume_id, user=request.user)
        result = {
            "title"   : resume.title,
            "isDone"  : resume.is_done,
            "isFile"  : resume.is_file,
            "fileUrl" : resume.file_url,
            "fileUuid" : resume.file_uuid,
            "content" : resume.content,
            "user"    : {
                "name" : request.user.name,
                "email": request.user.email,
            }
        }
        
        return JsonResponse({"message" : "SUCCESS", "result" : result}, status=200)

    @authorization
    def patch(self, request, resume_id):
        try:
            data   = json.loads(request.body)
            resume = Resume.objects.filter(id=resume_id, user=request.user)
            
            if not resume.exists():
                return JsonResponse({"message" : "RESUME_NOT_FOUND"}, status=401)
            
            resume.update(
                is_done = data["isDone"],
                title   = data["title"],
                content = {
                    "description" : data["description"],
                    "career"      : data["career"],
                    "education"   : data["education"],
                    "skill"       : data["skill"],
                },
                updated_at = timezone.now()
            )
            return JsonResponse({"message" : "SUCCESS"}, status=200)

        except JSONDecodeError:
            return JsonResponse({"message" : "JSON_DECODE_ERROR"}, status=400)

        except KeyError:
            return JsonResponse({"message" : "KEY_ERROR"}, status=400)
            
    @authorization
    def delete(self, request, resume_id):
        if not Resume.objects.filter(id=resume_id, user=request.user).exists():
            return JsonResponse({"message" : "RESUME_NOT_FOUND"}, status=401)

        Resume.objects.get(id=resume_id, user=request.user).delete()
        
        return JsonResponse({"message" : "SUCCESS"}, status=200)

class ResumeApply(View):
    @authorization
    def post(self, request):
        data           = json.loads(request.body)
        user           = request.user
        resume_id      = data["resume_id"]
        job_posting_id = data["job_posting_id"]

        apply = Apply.objects.create(
            user           = user,
            job_posting_id = job_posting_id
        )
        ResumeApply.objects.create(
            resume_id = resume_id,
            apply     = apply
        )

        return JsonResponse({"message":"SUCCESS"}, status = 201)

class ResumeFile(View):
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_S3_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_S3_SECRET_ACCESS_KEY,
    )

    @authorization
    def post(self, request):
        user      = request.user
        resume_id = request.GET.get("resume_id")

        if not len(request.FILES):
            return JsonResponse({"message": "FILE_NONE"}, status=404)

        for file in request.FILES.getlist('file'):
            resume, is_created = Resume.objects.get_or_create(
                id       = resume_id,
                user     = user,
                defaults = {
                    "user_id": user.id,
                    "title": "default",
                    "is_done": True,
                    "file_url": "default",
                    "is_file": True,
                    "file_uuid": str(uuid.uuid4())
                }
            )
            self.s3_client.upload_fileobj(
                file,
                BUCKET,
                resume.file_uuid,
                ExtraArgs = {
                    "ContentType": file.content_type,
                }
            )

            file_urls = f"{AWS_S3_URL}/{BUCKET}/{resume.file_uuid}"

            resume.file_url = file_urls
            resume.title    = file.name
            resume.save()

        return JsonResponse({"message": "SUCCESS"}, status=201)

    @authorization
    def delete(self, request, resume_id):
        user = request.user

        if not Resume.objects.filter(id=resume_id, user=user).exists():
            return JsonResponse({"message": "INVILD_RESUME"}, status=404)

        self.s3_client.delete_object(Bucket=BUCKET, Key=Resume.objects.get(id=resume_id, user=user).file_uuid)

        return JsonResponse({"message": "SUCCESS"}, status=200)
