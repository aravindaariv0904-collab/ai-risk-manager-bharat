import { useEffect, useState } from 'react'
import { supabase } from '../services/supabase'
import { Button } from '../components/ui/Button'
import { Label } from '../components/ui/Label'
import { Select } from '../components/ui/Select'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card'
import { Alert } from '../components/ui/Alert'
import type { Profile } from '../types'

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'hi', label: 'हिन्दी (Hindi)' },
  { value: 'ta', label: 'தமிழ் (Tamil)' },
]

export default function SettingsPage() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [language, setLanguage] = useState('en')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data }) => {
      if (!data.session) return
      const { data: userData } = await supabase
        .from('users')
        .select('*')
        .eq('auth_user_id', data.session.user.id)
        .maybeSingle()
      if (userData) {
        setProfile(userData as Profile)
        setLanguage(userData.language || 'en')
      }
    })
  }, [])

  async function saveLanguage() {
    if (!profile) return
    setSaving(true)
    setSaved(false)
    const { error } = await supabase
      .from('users')
      .update({ language })
      .eq('id', profile.id)
    if (!error) {
      setSaved(true)
      setProfile({ ...profile, language: language as Profile['language'] })
    }
    setSaving(false)
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Language only affects explanations. Risk scores are language-independent.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>{profile?.name}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="language">Preferred Language</Label>
            <Select value={language} onChange={(e) => setLanguage(e.target.value)} id="language">
              {LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </Select>
          </div>
          <Button onClick={saveLanguage} loading={saving}>
            Save Language
          </Button>
          {saved && <Alert variant="success">Language saved. Your AI explanations will update.</Alert>}
        </CardContent>
      </Card>
    </div>
  )
}