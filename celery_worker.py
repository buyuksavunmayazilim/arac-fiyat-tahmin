"""Celery Worker — PYTHONPATH=/home/arac olduğu için app modülü direkt import edilir."""

import os
from celery import Celery


def make_celery(flask_app):
    celery = Celery(
        flask_app.import_name,
        broker=flask_app.config["CELERY_BROKER_URL"],
        backend=flask_app.config["CELERY_RESULT_BACKEND"],
    )
    celery.conf.update(flask_app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


from app import create_app

flask_app = create_app()
flask_app.config["CELERY_BROKER_URL"] = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
flask_app.config["CELERY_RESULT_BACKEND"] = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery = make_celery(flask_app)


@celery.task(name="tasks.retrain_model")
def retrain_model():
    from ml.train import train_from_db
    return train_from_db()


@celery.task(name="tasks.warmup_predictor")
def warmup_predictor():
    from ml.predictor import get_predictor
    p = get_predictor()
    return {"loaded": p.is_loaded()}
