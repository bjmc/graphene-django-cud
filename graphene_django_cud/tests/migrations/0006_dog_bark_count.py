# Generated by Django 2.2.6 on 2021-01-02 02:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0005_dogregistration'),
    ]

    operations = [
        migrations.AddField(
            model_name='dog',
            name='bark_count',
            field=models.IntegerField(default=0),
        ),
    ]
