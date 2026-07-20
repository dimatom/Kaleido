from django.db import migrations, models


def migrate_is_parsed(apps, schema_editor):
    """将原 is_parsed=True 的文档迁移为 parse_status='parsed'"""
    Document = apps.get_model('rag_app', 'Document')
    Document.objects.filter(is_parsed=True).update(parse_status='parsed')


class Migration(migrations.Migration):
    dependencies = [
        ('rag_app', '0003_chatmessagehistory_chatsession'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='parse_status',
            field=models.CharField(
                choices=[
                    ('unparsed', '未解析'),
                    ('parsing', '解析中'),
                    ('parsed', '解析成功'),
                    ('failed', '解析失败'),
                ],
                default='unparsed',
                max_length=20,
                verbose_name='解析状态',
            ),
        ),
        migrations.RunPython(migrate_is_parsed, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='document',
            name='is_parsed',
        ),
    ]
