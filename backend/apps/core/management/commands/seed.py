"""Seed initial content: services + a sample blog post.

Idempotent - safe to re-run. Existing records are updated; nothing is deleted.
"""
from __future__ import annotations

from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.utils import timezone

from blog.models import Category, Post
from newsletter.models import Subscriber  # noqa: F401 (imported for migration safety)
from pages.models import Service

SERVICES = [
    {
        "name": "Risk",
        "tagline": "Identify gaps. Close them, fast.",
        "summary": (
            "We identify gaps between your required and actual security state and "
            "deliver realistic, prioritized remediation plans that you can execute "
            "as quickly as your business allows."
        ),
        "icon": "shield-exclamation",
        "order": 10,
        "is_featured": True,
        "body_markdown": (
            "## What you get\n\n"
            "- A current-state assessment scoped to your most critical assets.\n"
            "- A target-state design aligned with NIST CSF / ISO 27001 / CIS controls.\n"
            "- A remediation roadmap with effort, owner, and impact for every item.\n\n"
            "## When this fits\n\n"
            "If you have never had an outside set of eyes on your security posture, "
            "or if a recent audit raised more questions than answers, start here."
        ),
    },
    {
        "name": "Access",
        "tagline": "The right people, the right access, every time.",
        "summary": (
            "Identity and access management protects against external attackers and "
            "insider threats alike. We help you ensure only authorized employees "
            "have exactly the access they need."
        ),
        "icon": "key",
        "order": 20,
        "is_featured": True,
        "body_markdown": (
            "## Capabilities\n\n"
            "- SSO and federated identity design (Entra ID, Okta, Auth0).\n"
            "- Least-privilege policy review and refactoring.\n"
            "- Privileged access management.\n"
            "- Joiner / Mover / Leaver automation."
        ),
    },
    {
        "name": "Controls",
        "tagline": "Tailored policies, real protection.",
        "summary": (
            "Cybersecurity services help organizations protect data with tailored "
            "policies and controls. We design custom policies that prevent attacks "
            "without grinding the business to a halt."
        ),
        "icon": "adjustments-horizontal",
        "order": 30,
        "is_featured": True,
        "body_markdown": (
            "We focus on controls that work in your environment, not generic checklists. "
            "Expect specific configurations, runbooks, and clear ownership."
        ),
    },
    {
        "name": "Testing",
        "tagline": "Find it before they do.",
        "summary": (
            "Identify, treat, and report security vulnerabilities. We prioritize threats "
            "and minimize your attack surface with a steady cadence of testing."
        ),
        "icon": "beaker",
        "order": 40,
        "is_featured": True,
        "body_markdown": (
            "## Engagements\n\n"
            "- External and internal penetration testing.\n"
            "- Cloud configuration reviews (AWS, Azure, GCP).\n"
            "- Application security testing (SAST/DAST/SCA).\n"
            "- Tabletop exercises."
        ),
    },
    {
        "name": "Detection",
        "tagline": "See attacks early. Respond faster.",
        "summary": (
            "We support incident discovery and response, including threat intelligence, "
            "alerting design, and reporting that surfaces real issues without alert fatigue."
        ),
        "icon": "magnifying-glass",
        "order": 50,
        "is_featured": False,
        "body_markdown": (
            "Detection engineering is the work of turning your environment into a sensor. "
            "We help you decide what to log, where to log it, and what to alert on."
        ),
    },
    {
        "name": "Forensics",
        "tagline": "Investigate. Contain. Learn.",
        "summary": (
            "We establish incident triage and forensics procedures, train staff, and "
            "transfer the knowledge your team needs to operate after the engagement ends."
        ),
        "icon": "finger-print",
        "order": 60,
        "is_featured": False,
        "body_markdown": (
            "## Deliverables\n\n"
            "- An incident response playbook tailored to your environment.\n"
            "- Forensic readiness assessment.\n"
            "- Post-incident reviews that produce durable improvements."
        ),
    },
    {
        "name": "Recovery",
        "tagline": "Bounce back without the bruises.",
        "summary": (
            "Ensure smooth recovery from breaches. We minimize negative impacts so that "
            "the lasting damage to your operations and reputation is contained."
        ),
        "icon": "arrow-path",
        "order": 70,
        "is_featured": False,
        "body_markdown": (
            "Recovery is the part most plans get wrong. We pressure-test yours."
        ),
    },
    {
        "name": "Application Security",
        "tagline": "Ship secure software, not just fast software.",
        "summary": (
            "Secure your applications through security scans, result analysis, integration "
            "of security tools into CI/CD, threat modeling, and developer training."
        ),
        "icon": "code-bracket",
        "order": 80,
        "is_featured": True,
        "body_markdown": (
            "## Programs we run\n\n"
            "- Secure SDLC design and rollout.\n"
            "- Threat modeling workshops.\n"
            "- SAST/DAST/SCA tooling selection and integration.\n"
            "- Developer security training tailored to your stack."
        ),
    },
]


SAMPLE_POST = {
    "title": "Why your cloud baseline matters more than your next tool",
    "slug": "cloud-baseline-matters-more",
    "excerpt": (
        "Most cloud incidents we are called in to investigate trace back to "
        "misconfiguration, not exotic exploits. A solid baseline beats a new tool."
    ),
    "body_markdown": (
        "## The pattern\n\n"
        "After enough incident reviews you start to see the same shape: a "
        "public storage bucket, an over-permissive IAM role, an unrotated key, "
        "a forgotten test environment. The attackers were not sophisticated. "
        "The configuration was.\n\n"
        "## What a baseline buys you\n\n"
        "- Predictable controls across every account and project.\n"
        "- Auditable, version-controlled policies instead of click-ops drift.\n"
        "- A clear line between 'this is broken' and 'this is by design'.\n\n"
        "## Where to start\n\n"
        "1. Pick a reference: CIS Benchmarks, AWS Security Reference Architecture, "
        "   Azure Cloud Adoption Framework.\n"
        "2. Encode the parts that matter to your business in IaC.\n"
        "3. Detect drift continuously, not at audit time.\n\n"
        "Your next tool can wait. Your baseline cannot."
    ),
    "meta_description": (
        "Most cloud breaches come from misconfiguration. Here is why a solid baseline "
        "outperforms any new tool, and where to start building one."
    ),
}


class Command(BaseCommand):
    help = "Seed services + a sample blog post for a brand-new install."

    def handle(self, *args, **options) -> None:
        site = Site.objects.get(pk=1)
        if site.domain in ("example.com", "localhost") or site.name != "Elbrus Cloud":
            site.domain = "elbruscloud.example"
            site.name = "Elbrus Cloud"
            site.save()
            self.stdout.write(self.style.SUCCESS("Updated default Site."))

        created_count = 0
        updated_count = 0
        for index, payload in enumerate(SERVICES):
            obj, created = Service.objects.update_or_create(
                name=payload["name"],
                defaults={
                    "tagline": payload["tagline"],
                    "summary": payload["summary"],
                    "body_markdown": payload["body_markdown"],
                    "icon": payload["icon"],
                    "order": payload["order"],
                    "is_featured": payload["is_featured"],
                    "is_published": True,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Services: {created_count} created, {updated_count} updated."
            )
        )

        category, _ = Category.objects.get_or_create(
            slug="cloud-security",
            defaults={
                "name": "Cloud Security",
                "description": "Practical guidance on securing cloud environments.",
            },
        )

        post, post_created = Post.objects.get_or_create(
            slug=SAMPLE_POST["slug"],
            defaults={
                "title": SAMPLE_POST["title"],
                "excerpt": SAMPLE_POST["excerpt"],
                "body_markdown": SAMPLE_POST["body_markdown"],
                "meta_description": SAMPLE_POST["meta_description"],
                "category": category,
                "status": Post.Status.PUBLISHED,
                "published_at": timezone.now(),
                "hero_image_alt": "Snow-capped mountain peak under a clear sky.",
            },
        )
        if post_created:
            self.stdout.write(self.style.SUCCESS(f"Sample post created: {post.title}"))
        else:
            self.stdout.write(f"Sample post already present: {post.title}")

        self.stdout.write(self.style.SUCCESS("Seed complete."))
