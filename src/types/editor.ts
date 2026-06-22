export interface WorldConfig {
  intro?: string;
  genre?: string;
  power_system?: any;
  protagonist?: {
    name?: string;
    background?: string;
    abilities?: string[];
  };
  locations?: string[];
  factions?: string[];
  rules?: string[];
  timeline?: string[];
}

export interface Volume {
  title: string;
  goal: string;
  estimated_chapters: number;
  antagonist?: any;
  key_events?: string[];
}

export interface Chapter {
  chapter_num: number;
  title: string;
  summary: string;
  content?: string;
}

export interface BookPlan {
  main_story: string;
  volumes: Volume[];
  current_volume?: number;
}

export interface HeroStatus {
  level?: number;
  cultivation_realm?: string;
  strength?: number;
  intelligence?: number;
  agility?: number;
  constitution?: number;
  special_abilities?: string[];
  equipment?: string[];
  achievements?: string[];
}

export interface Character {
  id: string;
  name: string;
  role: 'main' | 'support' | 'antagonist';
  description: string;
  avatar?: string;
}

export interface Location {
  id: string;
  name: string;
  description: string;
  type: 'city' | 'mountain' | 'forest' | 'sea' | 'cave' | 'other';
}

export interface PlotEvent {
  id: string;
  chapter: number;
  title: string;
  description: string;
  type: 'battle' | 'discovery' | 'relationship' | 'revelation' | 'other';
}
