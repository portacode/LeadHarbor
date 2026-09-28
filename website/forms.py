from django import forms
from django.utils import timezone
from .models import FormField

class ConversionForm(forms.Form):
    website = forms.CharField(required=False, widget=forms.HiddenInput)
    consent = forms.BooleanField(label='I agree to be contacted about this request.')
    def __init__(self, *args, booking=False, **kwargs):
        super().__init__(*args, **kwargs)
        dynamic = {}
        for item in FormField.objects.filter(enabled=True):
            options = {'label': item.label, 'required': item.required}
            if item.kind == 'email': field = forms.EmailField(max_length=254, **options)
            elif item.kind == 'textarea': field = forms.CharField(max_length=3000, widget=forms.Textarea(attrs={'rows':3}), **options)
            elif item.kind == 'select': field = forms.ChoiceField(choices=[('', 'Please choose')] + [(v.strip(),v.strip()) for v in item.choices.splitlines() if v.strip()], **options)
            elif item.kind == 'date': field = forms.DateField(widget=forms.DateInput(attrs={'type':'date'}), **options)
            elif item.kind == 'checkbox': field = forms.BooleanField(**options)
            else: field = forms.CharField(max_length=300, **options)
            dynamic[item.key] = field
        if booking and 'preferred_date' not in dynamic:
            dynamic['preferred_date'] = forms.DateField(label='Preferred date', required=True, widget=forms.DateInput(attrs={'type':'date', 'min':timezone.localdate().isoformat()}))
        self.fields = {**dynamic, **self.fields}
    def clean(self):
        data = super().clean()
        if data.get('website'): raise forms.ValidationError('Unable to submit this request.')
        if data.get('preferred_date') and data['preferred_date'] < timezone.localdate():
            self.add_error('preferred_date', 'Choose today or a future date.')
        return data
