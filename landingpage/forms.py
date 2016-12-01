from django import forms


class EmailForm(forms.Form):
    your_name = forms.EmailField(label='Votre addresse email', max_length=100)
